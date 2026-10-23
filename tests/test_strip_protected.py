"""Tests for scripts/strip_protected.py - the pipeline removes what breaks a
protected name instead of the gate refusing the whole release.

On 27 of the nights between 2026-09-18 and 2026-10-22 the release was refused
because four CDN apexes reached the list through Adblock rules with a path. The
published list froze for 35 days. These tests hold the replacement to two
things: the list that ships never breaks a protected name, and nothing else is
removed on the way.
"""

import json

import pytest

from check_quality import protected_violations, read_domain_list


def run_strip(tmp_path, monkeypatch, blacklist, protected):
    import strip_protected

    (tmp_path / 'sources').mkdir(exist_ok=True)
    (tmp_path / 'sources' / 'protected.txt').write_text(
        '\n'.join(protected) + '\n', encoding='utf-8')
    bl = tmp_path / 'all.fqdn.blacklist'
    bl.write_text(''.join(f'{d}\n' for d in blacklist), encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(strip_protected, 'PROTECTED', strip_protected.Path('sources/protected.txt'))
    monkeypatch.setattr('sys.argv', ['strip_protected.py', '--blacklist', str(bl),
                                     '--sources-dir', str(tmp_path / 'sources_raw')])
    code = strip_protected.main()

    remaining = bl.read_text(encoding='utf-8').split()
    report_path = tmp_path / 'sources_raw' / 'protected_stripped.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
    return code, remaining, report


def test_a_protected_name_is_removed_and_the_rest_is_untouched(tmp_path, monkeypatch):
    code, remaining, report = run_strip(
        tmp_path, monkeypatch,
        blacklist=['ads.example', 'akamai.net', 'tracker.example'],
        protected=['akamai.net  # Akamai'],
    )
    assert code == 0
    assert remaining == ['ads.example', 'tracker.example']
    assert report['stripped'] == [{
        'removed': 'akamai.net', 'protects': ['akamai.net'],
        'reason': 'Akamai', 'sources': [],
    }]


def test_every_ancestor_goes_not_only_the_closest(tmp_path, monkeypatch):
    """Removing ocsp.digicert.com while digicert.com stays would leave the
    protected name exactly as broken on Unbound and AdGuard Home."""
    code, remaining, report = run_strip(
        tmp_path, monkeypatch,
        blacklist=['digicert.com', 'ocsp.digicert.com', 'ads.example'],
        protected=['ocsp.digicert.com  # DigiCert OCSP responder'],
    )
    assert code == 0
    assert remaining == ['ads.example']
    assert sorted(e['removed'] for e in report['stripped']) == ['digicert.com', 'ocsp.digicert.com']


def test_a_block_below_a_protected_name_stays(tmp_path, monkeypatch):
    """Blocking one site on a hosting platform is what the list is for."""
    code, remaining, report = run_strip(
        tmp_path, monkeypatch,
        blacklist=['malware.pages.dev', 'phish.azurewebsites.net'],
        protected=['pages.dev  # Cloudflare Pages apex', 'azurewebsites.net  # Azure'],
    )
    assert code == 0
    assert remaining == ['malware.pages.dev', 'phish.azurewebsites.net']
    assert report['stripped'] == []


def test_the_output_never_breaks_a_protected_name(tmp_path, monkeypatch):
    """The property the gate checks, asserted on the stripped output with the
    gate's own function. Break-test: make strip() a no-op and this fails."""
    protected = ['akamai.net  # Akamai', 'cloudfront.net  # CloudFront',
                 'ocsp.digicert.com  # OCSP', '2.android.pool.ntp.org  # NTP']
    code, remaining, _ = run_strip(
        tmp_path, monkeypatch,
        blacklist=['akamai.net', 'cloudfront.net', 'digicert.com', 'pool.ntp.org',
                   'ntp.org', 'ads.example', 'x.cloudfront.net'],
        protected=protected,
    )
    assert code == 0
    names = read_domain_list(tmp_path / 'sources' / 'protected.txt')
    assert protected_violations(names, set(remaining)) == []
    assert 'ads.example' in remaining and 'x.cloudfront.net' in remaining


def test_an_empty_protected_list_stops_the_build(tmp_path, monkeypatch):
    """A missing protected.txt would make this step a silent no-op that looks
    exactly like a clean night."""
    code, remaining, _ = run_strip(
        tmp_path, monkeypatch, blacklist=['akamai.net'], protected=['# nothing'],
    )
    assert code == 1
    assert remaining == ['akamai.net']


def test_the_gate_reports_what_was_stripped_and_passes(tmp_path, monkeypatch):
    """The two steps in the order the pipeline runs them: what the strip
    removed reaches quality.json, and the gate has nothing left to refuse."""
    from test_check_quality import run_gate

    run_strip(tmp_path, monkeypatch,
              blacklist=['ads.example', 'akamai.net'],
              protected=['akamai.net  # Akamai'])
    stripped_list = (tmp_path / 'all.fqdn.blacklist').read_text(encoding='utf-8').split()

    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=stripped_list,
        protected=['akamai.net  # Akamai'],
        acknowledged=[],
        ranks={},
        extra_argv=['--sources-dir', str(tmp_path / 'sources_raw')],
    )
    assert code == 0
    assert report['protected']['violations'] == []
    assert [e['removed'] for e in report['protected']['stripped']] == ['akamai.net']


def test_the_gate_still_refuses_when_the_strip_did_not_run(tmp_path, monkeypatch):
    """The gate stays the second line: an unstripped list must still fail."""
    from test_check_quality import run_gate

    code, report = run_gate(
        tmp_path, monkeypatch,
        blacklist=['ads.example', 'akamai.net'],
        protected=['akamai.net  # Akamai'],
        acknowledged=[],
        ranks={},
    )
    assert code == 1
    assert report['protected']['violations'][0]['domain'] == 'akamai.net'
