"""Tests for scripts/build_site.py - the lookup index the website queries.

The index is the only thing standing between a user's question and a wrong
answer about whether a domain is blocked, so the properties pinned here are
correctness ones: every domain must be findable in the shard its hash names,
every shard a client can ask for must exist, and a truncated input must stop the
build instead of quietly publishing a smaller list.
"""

import hashlib
import json

import pytest

from build_site import (
    PREFIX_LEN,
    SHARD_COUNT,
    build_shards,
    file_sha256,
    iter_domains,
    load_history,
)


@pytest.fixture
def blacklist(tmp_path):
    """A blacklist artifact shaped like the published one, header included."""
    path = tmp_path / 'blacklist.txt'
    domains = [f'domain{i:06d}.example' for i in range(2000)]
    path.write_text(
        '# Aggregated by fabriziosalmi/blacklists\n'
        '# Domains: 2000\n'
        '\n'
        + '\n'.join(domains) + '\n',
        encoding='utf-8',
    )
    return path, domains


def test_iter_domains_skips_header_and_blanks(blacklist):
    path, domains = blacklist
    assert list(iter_domains(path)) == domains


def test_iter_domains_lowercases():
    """Shard placement is computed from the domain, so case must be settled
    before hashing or a lookup for the same name lands in a different shard."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'b.txt'
        path.write_text('Example.COM\n', encoding='utf-8')
        assert list(iter_domains(path)) == ['example.com']


def test_every_domain_is_in_the_shard_its_hash_names(blacklist, tmp_path, monkeypatch):
    """The round trip a browser performs: hash, fetch one shard, expect a hit."""
    path, domains = blacklist
    monkeypatch.setattr('build_site.MIN_PLAUSIBLE_DOMAINS', 1)

    out = tmp_path / 'site'
    total = build_shards(path, out)
    assert total == len(domains)

    shard_dir = out / 'data' / 'shards'
    for domain in domains:
        shard = hashlib.sha256(domain.encode()).hexdigest()[:PREFIX_LEN]
        content = (shard_dir / f'{shard}.txt').read_text(encoding='utf-8')
        assert domain in content.split('\n')


def test_absent_domain_is_not_reported_as_listed(blacklist, tmp_path, monkeypatch):
    path, _ = blacklist
    monkeypatch.setattr('build_site.MIN_PLAUSIBLE_DOMAINS', 1)
    out = tmp_path / 'site'
    build_shards(path, out)

    absent = 'definitely-not-listed.example'
    shard = hashlib.sha256(absent.encode()).hexdigest()[:PREFIX_LEN]
    content = (out / 'data' / 'shards' / f'{shard}.txt').read_text(encoding='utf-8')
    assert absent not in content.split('\n')


def test_all_shards_exist_even_when_empty(blacklist, tmp_path, monkeypatch):
    """A missing shard would 404, and the client cannot tell a 404 apart from
    "not listed" - it would have to guess, which is the thing to avoid."""
    path, _ = blacklist
    monkeypatch.setattr('build_site.MIN_PLAUSIBLE_DOMAINS', 1)
    out = tmp_path / 'site'
    build_shards(path, out)

    shards = list((out / 'data' / 'shards').glob('*.txt'))
    assert len(shards) == SHARD_COUNT


def test_truncated_input_aborts_the_build(tmp_path):
    """Publishing a half-downloaded list looks exactly like a real update."""
    path = tmp_path / 'blacklist.txt'
    path.write_text('only-one.example\n', encoding='utf-8')

    with pytest.raises(SystemExit) as exc:
        build_shards(path, tmp_path / 'site')
    assert 'truncated' in str(exc.value).lower()


def test_shards_are_rebuilt_not_appended(blacklist, tmp_path, monkeypatch):
    """Two builds in the same directory must not double every entry."""
    path, domains = blacklist
    monkeypatch.setattr('build_site.MIN_PLAUSIBLE_DOMAINS', 1)
    out = tmp_path / 'site'

    build_shards(path, out)
    build_shards(path, out)

    shard_dir = out / 'data' / 'shards'
    lines = sum(
        len([l for l in f.read_text(encoding='utf-8').split('\n') if l])
        for f in shard_dir.glob('*.txt')
    )
    assert lines == len(domains)


def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / 'f.bin'
    payload = b'some bytes' * 1000
    path.write_bytes(payload)
    assert file_sha256(path) == hashlib.sha256(payload).hexdigest()


def test_load_history_sorts_and_skips_malformed_rows(tmp_path):
    path = tmp_path / 'history.csv'
    path.write_text(
        'date,total_domains,whitelisted,sources\n'
        '2026-01-03,300,3,10\n'
        '2026-01-01,100,1,10\n'
        'broken,not-a-number,1,10\n'
        '2026-01-02,200,2,10\n',
        encoding='utf-8',
    )
    history = load_history(path)
    assert [h['date'] for h in history] == ['2026-01-01', '2026-01-02', '2026-01-03']
    assert [h['total_domains'] for h in history] == [100, 200, 300]


def test_load_history_returns_empty_when_missing(tmp_path):
    assert load_history(tmp_path / 'nope.csv') == []


# --------------------------------------------------------------------------
# stats.json must carry everything that was merged into it
#
# Twice now a new block was added after stats.json had already been written, so
# the value was computed, discarded and silently absent from the site. Ordering
# is easy to get wrong and invisible when it is, so it is pinned here rather
# than left to review.
# --------------------------------------------------------------------------

def build_minimal_site(tmp_path, monkeypatch, extra_stats=None):
    import build_site

    repo = tmp_path / 'repo'
    (repo / 'sources').mkdir(parents=True)
    (repo / 'stats').mkdir()
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'index.html').write_text('<h1>site</h1>', encoding='utf-8')

    (repo / 'sources' / 'registry.json').write_text(json.dumps({
        'sources': [{
            'id': 'example', 'url': 'https://example.org/l.txt', 'name': 'Example',
            'project': 'example', 'maintainer': 'Example', 'homepage': 'https://example.org',
            'categories': ['ads'],
            'license': {'spdx': 'MIT', 'name': 'MIT', 'url': 'https://example.org/L',
                        'verified': True, 'evidence': 'github-api', 'checked_at': '2026-01-01'},
        }],
    }), encoding='utf-8')

    (repo / 'stats' / 'daily_stats.json').write_text(json.dumps({
        'whitelisted_domains': 5, 'blacklist_sources': 1, 'changes': {},
    }), encoding='utf-8')
    (repo / 'stats' / 'whitelist.json').write_text(json.dumps({
        'unique': 7, 'active': 3, 'dormant': 4,
    }), encoding='utf-8')
    (repo / 'stats' / 'classification.json').write_text(json.dumps({
        'categories': [{'category': 'adult', 'domains': 42, 'percent': 1.5}],
        'reference': {'name': 'Reference list'},
    }), encoding='utf-8')

    for name, payload in (extra_stats or {}).items():
        (repo / 'stats' / name).write_text(json.dumps(payload), encoding='utf-8')

    blacklist = tmp_path / 'blacklist.txt'
    blacklist.write_text(
        '\n'.join(f'domain{i:05d}.example' for i in range(100)) + '\n',
        encoding='utf-8',
    )

    monkeypatch.setattr(build_site, 'MIN_PLAUSIBLE_DOMAINS', 1)
    monkeypatch.setattr('sys.argv', [
        'build_site.py', '--repo-path', str(repo),
        '--blacklist', str(blacklist), '--out', str(tmp_path / 'site'),
    ])
    build_site.main()

    return json.loads(
        (tmp_path / 'site' / 'data' / 'stats.json').read_text(encoding='utf-8'))


def test_stats_json_carries_the_whitelist_summary(tmp_path, monkeypatch):
    stats = build_minimal_site(tmp_path, monkeypatch)
    assert stats['whitelist'] == {'entries': 7, 'active': 3, 'dormant': 4}


def test_stats_json_carries_the_content_classification(tmp_path, monkeypatch):
    stats = build_minimal_site(tmp_path, monkeypatch)
    assert stats['classified_categories'] == [
        {'category': 'adult', 'domains': 42, 'percent': 1.5}
    ]
    assert stats['classification_reference']['name'] == 'Reference list'


def test_the_whitelist_count_comes_from_the_current_run(tmp_path, monkeypatch):
    """daily_stats.json says 5, the run that built the artifact says 7."""
    stats = build_minimal_site(tmp_path, monkeypatch)
    assert stats['whitelisted_domains'] == 7


def test_the_source_count_comes_from_the_registry(tmp_path, monkeypatch):
    stats = build_minimal_site(tmp_path, monkeypatch)
    assert stats['blacklist_sources'] == 1
