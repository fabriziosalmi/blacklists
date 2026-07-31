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
