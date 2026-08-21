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

def run_gate(tmp_path, monkeypatch, blacklist, protected, acknowledged, ranks,
             load_tranco=None, previous=None):
    """Drive main() against a synthetic list, with no network access.

    ``load_tranco`` replaces the ranking fetch outright, so a test can simulate
    the download failing rather than returning data.
    """
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
    monkeypatch.setattr(check_quality, 'load_tranco',
                        load_tranco or (lambda cache: ranks))
    argv = ['check_quality.py', '--blacklist', str(bl)]
    if previous is not None:
        prev = tmp_path / 'previous.txt'
        prev.write_text('\n'.join(previous) + '\n', encoding='utf-8')
        argv += ['--previous', str(prev)]
    monkeypatch.setattr('sys.argv', argv)

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
        previous=['doubleclick.net'],
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
        previous=[],            # it was not in the list before
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


def test_an_unreachable_ranking_does_not_fail_the_release(tmp_path, monkeypatch):
    """A third-party download being down says nothing about the list. Refusing
    to ship a correct blacklist because tranco-list.eu is having a bad afternoon
    would help nobody, so the popularity checks are skipped and the
    network-independent protected check still stands."""
    def explode(cache):
        raise OSError('name resolution failed')

    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['ads.example'],
        protected=['github.com  # source hosting'],
        acknowledged=[],
        ranks={},
        load_tranco=explode,
    )
    assert code == 0
    assert report['ranking_available'] is False


def test_a_protected_domain_still_fails_when_the_ranking_is_unreachable(tmp_path, monkeypatch):
    """The safety-critical half of the gate needs no network and must not be
    disabled by the loss of the optional half."""
    def explode(cache):
        raise OSError('name resolution failed')

    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['cloudflare-dns.com'],
        protected=['cloudflare-dns.com  # DoH endpoint'],
        acknowledged=[],
        ranks={},
        load_tranco=explode,
    )
    assert code == 1
    assert report['protected']['violations'][0]['domain'] == 'cloudflare-dns.com'


# --------------------------------------------------------------------------
# Size regression
# --------------------------------------------------------------------------

def test_a_large_overnight_loss_is_refused():
    """The 2026-07-31 failure: two sources 404'd and took 46% of the list.
    Forty-four of forty-six sources still downloaded, so counting sources saw
    nothing wrong."""
    from check_quality import check_shrinkage

    ok, message = check_shrinkage(2_754_896, 4_755_218)
    assert not ok
    assert '42.1%' in message


def test_normal_daily_churn_is_accepted():
    from check_quality import check_shrinkage

    ok, _ = check_shrinkage(4_700_000, 4_755_218)   # -1.2%
    assert ok


def test_growth_is_never_blocked():
    """Adding coverage is the normal outcome of fixing a parser."""
    from check_quality import check_shrinkage

    ok, _ = check_shrinkage(5_114_007, 4_755_218)   # +7.5%
    assert ok


def test_a_first_run_with_no_history_is_accepted():
    from check_quality import check_shrinkage

    ok, message = check_shrinkage(1000, None)
    assert ok
    assert 'no previous total' in message


def test_the_boundary_is_not_off_by_one():
    from check_quality import check_shrinkage

    assert check_shrinkage(900, 1000)[0]        # exactly -10%, accepted
    assert not check_shrinkage(899, 1000)[0]    # -10.1%, refused


def test_previous_total_reads_the_last_history_row(tmp_path):
    from check_quality import previous_total

    history = tmp_path / 'history.csv'
    history.write_text(
        'date,total_domains,whitelisted,sources\n'
        '2026-07-30,4742184,2059,50\n'
        '2026-07-31,4755218,2059,50\n',
        encoding='utf-8',
    )
    assert previous_total(history) == 4755218


def test_previous_total_is_none_without_history(tmp_path):
    from check_quality import previous_total
    assert previous_total(tmp_path / 'absent.csv') is None


# --------------------------------------------------------------------------
# Rank drift is not a new block
# --------------------------------------------------------------------------

def test_a_domain_that_merely_became_popular_does_not_fail_the_release(tmp_path, monkeypatch):
    """The outage of August 2026, written down.

    Tranco reranks daily, so a long-blocked domain crosses the rank-1000
    boundary on its own. The gate read that as a new block and stopped every
    release for ten nights; six of the seven domains it flagged had been in the
    list for weeks, and the published blacklist went two weeks stale.
    """
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['parklogic.com'],
        protected=[],
        acknowledged=[],
        ranks={'parklogic.com': 771},       # newly inside the review band
        previous=['parklogic.com'],         # but blocked for weeks already
    )
    assert code == 0
    assert report['popularity']['unacknowledged'] == []


def test_a_genuinely_new_popular_block_still_fails_the_release(tmp_path, monkeypatch):
    """The case the gate exists for: an upstream list starts blocking something
    widely used, and it was not in yesterday's release."""
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['newly-blocked.example', 'old.example'],
        protected=[],
        acknowledged=[],
        ranks={'newly-blocked.example': 300, 'old.example': 400},
        previous=['old.example'],
    )
    assert code == 1
    assert [e['domain'] for e in report['popularity']['unacknowledged']] == \
        ['newly-blocked.example']


def test_the_band_is_reported_not_enforced_without_a_previous_release(tmp_path, monkeypatch):
    """Without the comparison the two cases are indistinguishable, so the gate
    reports rather than blocking - a first run must not be unpublishable."""
    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['popular.example'],
        protected=[],
        acknowledged=[],
        ranks={'popular.example': 10},
        previous=None,
    )
    assert code == 0
    assert report['popularity']['enforced'] is False


def test_an_acknowledged_new_block_does_not_fail_the_release(tmp_path, monkeypatch):
    code, _ = run_gate(
        tmp_path, monkeypatch,
        blacklist=['reviewed.example'],
        protected=[],
        acknowledged=['reviewed.example  # deliberate, checked on 2026-08-21'],
        ranks={'reviewed.example': 500},
        previous=[],
    )
    assert code == 0


def test_a_protected_domain_fails_even_with_a_previous_release(tmp_path, monkeypatch):
    """Relaxing the review band must not weaken the safety-critical check."""
    code, _ = run_gate(
        tmp_path, monkeypatch,
        blacklist=['cloudflare-dns.com'],
        protected=['cloudflare-dns.com  # DoH endpoint'],
        acknowledged=[],
        ranks={'cloudflare-dns.com': 5000},
        previous=['cloudflare-dns.com'],
    )
    assert code == 1
