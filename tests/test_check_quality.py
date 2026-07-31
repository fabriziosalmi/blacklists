"""Tests for scripts/check_quality.py - the gate that can stop a release.

A gate that fails when it should not is a gate someone disables, so these pin
both directions: it must fire on a protected domain, and it must stay silent
for the popular domains this project blocks on purpose.
"""

import json

import pytest

from check_quality import attribute, load_blacklist, read_domain_list


# --------------------------------------------------------------------------
# Curated list parsing
# --------------------------------------------------------------------------

def test_reasons_are_kept_with_their_domain(tmp_path):
    """A bare domain loses why it is protected, and an entry nobody can justify
    is an entry nobody dares remove."""
    path = tmp_path / 'protected.txt'
    path.write_text(
        '# A header comment\n'
        '\n'
        'example.com  # because it matters\n'
        'bare.example\n',
        encoding='utf-8',
    )
    entries = read_domain_list(path)
    assert entries == {'example.com': 'because it matters', 'bare.example': None}


def test_domains_are_lowercased(tmp_path):
    path = tmp_path / 'protected.txt'
    path.write_text('Example.COM  # mixed case\n', encoding='utf-8')
    assert 'example.com' in read_domain_list(path)


def test_missing_file_is_an_empty_list_not_an_error(tmp_path):
    assert read_domain_list(tmp_path / 'nope.txt') == {}


def test_blacklist_header_is_not_read_as_a_domain(tmp_path):
    path = tmp_path / 'bl.txt'
    path.write_text(
        '# Aggregated by fabriziosalmi/blacklists\n'
        '# Domains: 2\n'
        'one.example\n'
        'TWO.example\n',
        encoding='utf-8',
    )
    assert load_blacklist(path) == {'one.example', 'two.example'}


# --------------------------------------------------------------------------
# The gate itself
# --------------------------------------------------------------------------

def run_gate(tmp_path, monkeypatch, blacklist, protected, acknowledged, ranks):
    """Drive main() against a synthetic list, with no network access."""
    import check_quality

    (tmp_path / 'sources').mkdir(exist_ok=True)
    (tmp_path / 'stats').mkdir(exist_ok=True)

    bl = tmp_path / 'bl.txt'
    bl.write_text('\n'.join(blacklist) + '\n', encoding='utf-8')
    (tmp_path / 'sources' / 'protected.txt').write_text(
        '\n'.join(protected) + '\n', encoding='utf-8')
    (tmp_path / 'sources' / 'acknowledged.txt').write_text(
        '\n'.join(acknowledged) + '\n', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_quality, 'PROTECTED', check_quality.Path('sources/protected.txt'))
    monkeypatch.setattr(check_quality, 'ACKNOWLEDGED', check_quality.Path('sources/acknowledged.txt'))
    monkeypatch.setattr(check_quality, 'REGISTRY', check_quality.Path('sources/registry.json'))
    monkeypatch.setattr(check_quality, 'OUTPUT', check_quality.Path('stats/quality.json'))
    monkeypatch.setattr(check_quality, 'load_tranco', lambda cache: ranks)
    monkeypatch.setattr('sys.argv', ['check_quality.py', '--blacklist', str(bl)])

    code = check_quality.main()
    report = json.loads((tmp_path / 'stats' / 'quality.json').read_text(encoding='utf-8'))
    return code, report


def test_a_protected_domain_fails_the_release(tmp_path, monkeypatch):
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['ads.example', 'cloudflare-dns.com'],
        protected=['cloudflare-dns.com  # DoH endpoint'],
        acknowledged=[],
        ranks={'cloudflare-dns.com': 5000},
    )
    assert code == 1
    assert report['protected']['violations'][0]['domain'] == 'cloudflare-dns.com'
    assert report['protected']['violations'][0]['reason'] == 'DoH endpoint'


def test_a_popular_ad_domain_does_not_fail_the_release(tmp_path, monkeypatch):
    """1,881 domains in the global top 10,000 are blocked on purpose. A gate
    that fired on popularity alone would fail on the project's whole point."""
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['doubleclick.net'],
        protected=['github.com  # source hosting'],
        acknowledged=['doubleclick.net  # rank 36 - reviewed'],
        ranks={'doubleclick.net': 36},
    )
    assert code == 0
    assert report['popularity']['blocked_in_band']['top_1000'] == 1
    assert report['popularity']['unacknowledged'] == []


def test_an_unreviewed_top_1000_entry_fails_the_release(tmp_path, monkeypatch):
    """The upstream-changed-under-us case: something new and very popular."""
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['roblox.com'],
        protected=[],
        acknowledged=[],
        ranks={'roblox.com': 56},
    )
    assert code == 1
    assert [e['domain'] for e in report['popularity']['unacknowledged']] == ['roblox.com']


def test_a_popular_domain_outside_the_review_band_is_only_reported(tmp_path, monkeypatch):
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['somewhere.example'],
        protected=[],
        acknowledged=[],
        ranks={'somewhere.example': 50_000},
    )
    assert code == 0
    assert report['popularity']['blocked_in_band']['top_100000'] == 1
    assert report['popularity']['unacknowledged'] == []


def test_report_ranks_the_most_popular_blocked_domains_first(tmp_path, monkeypatch):
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['low.example', 'high.example'],
        protected=[],
        acknowledged=['high.example  # reviewed'],
        ranks={'high.example': 10, 'low.example': 900_000},
    )
    assert code == 0
    ordering = [e['domain'] for e in report['popularity']['most_popular_blocked']]
    assert ordering == ['high.example', 'low.example']


# --------------------------------------------------------------------------
# Attribution
# --------------------------------------------------------------------------

def test_attribution_names_the_source_that_supplied_a_domain(tmp_path):
    sources = tmp_path / 'sources_raw'
    sources.mkdir()
    (sources / '000.meta').write_text(
        '0\thttps://example.org/list.txt\t200\t100\t1\n', encoding='utf-8')
    (sources / '000.fqdn.list').write_text(
        '0.0.0.0 tracked.example\n', encoding='utf-8')

    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({
        'sources': [{'url': 'https://example.org/list.txt', 'name': 'Example List'}]
    }), encoding='utf-8')

    assert attribute({'tracked.example'}, sources, registry) == {
        'tracked.example': ['Example List']
    }


def test_attribution_degrades_quietly_without_the_downloads(tmp_path):
    """The report is still worth publishing when run outside the pipeline."""
    assert attribute({'a.example'}, tmp_path / 'absent', tmp_path / 'none.json') == {}
