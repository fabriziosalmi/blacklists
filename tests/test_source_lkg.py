"""Tests for scripts/source_lkg.py - the last-known-good copy of each source.

A source that fails or collapses for a night is served from the copy kept on
its last good night, for at most seven days. The thresholds come from 93 days
of release logs: no source ever lost more than 25% in a day in normal
operation, and two real outages (hagezi 404 on 2026-08-10, UT1 404 on
2026-10-22) each took 10% to 49% of the list with them.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import source_lkg
from source_lkg import apply, save, url_key

NOW = datetime(2026, 10, 23, 0, 30, tzinfo=timezone.utc)
URL_A = 'https://example.org/a.txt'
URL_B = 'https://example.org/b.txt'


def lines(n, prefix='d'):
    return ''.join(f'{prefix}{i}.example\n' for i in range(n))


def write_source(sources, index, url, body=None, status='200'):
    """A download as generate.sh leaves it: a meta record, and a list only
    when the fetch returned a 2xx."""
    sources.mkdir(exist_ok=True)
    (sources / f'{index:03d}.meta').write_text(
        f'{index}\t{url}\t{status}\t0\t0\n', encoding='utf-8')
    if body is not None:
        (sources / f'{index:03d}.fqdn.list').write_text(body, encoding='utf-8')


def keep(lkg, url, body, saved_at):
    lkg.mkdir(exist_ok=True)
    key = url_key(url)
    (lkg / f'{key}.list').write_text(body, encoding='utf-8')
    manifest_path = lkg / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest[key] = {'url': url, 'saved_at': saved_at.isoformat(),
                     'entries': len(body.splitlines())}
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')


@pytest.fixture
def dirs(tmp_path):
    return tmp_path / 'sources_raw', tmp_path / 'sources_lkg'


def fallback_of(sources, index):
    path = sources / f'{index:03d}.fallback'
    return json.loads(path.read_text()) if path.exists() else None


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def test_a_failed_download_is_served_from_the_kept_copy(dirs):
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=None, status='404')
    keep(lkg, URL_A, lines(5000), NOW - timedelta(days=1))

    apply(sources, lkg, NOW)

    assert (sources / '000.fqdn.list').read_text() == lines(5000)
    record = fallback_of(sources, 0)
    assert record['reason'] == 'download failed'
    assert record['http_status'] == '404'
    assert record['kept_age_days'] == 1.0


def test_a_collapsed_source_is_served_from_the_kept_copy(dirs):
    """A 200 that carries 40% fewer entries than yesterday has never happened
    in normal operation; a truncated body or an error page looks like this."""
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=lines(6000))
    keep(lkg, URL_A, lines(10000), NOW - timedelta(days=1))

    apply(sources, lkg, NOW)

    assert len((sources / '000.fqdn.list').read_text().splitlines()) == 10000
    assert fallback_of(sources, 0)['reason'].startswith('collapsed from 10,000 to 6,000')


def test_the_worst_measured_normal_night_is_not_a_collapse(dirs):
    """hagezi TIF lost 24.2% on 2026-10-08 and that was the feed doing its
    job. Break-test: lower MAX_SHRINK_FRACTION to 0.2 and this fails."""
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=lines(7580))
    keep(lkg, URL_A, lines(10000), NOW - timedelta(days=1))

    apply(sources, lkg, NOW)

    assert len((sources / '000.fqdn.list').read_text().splitlines()) == 7580
    assert fallback_of(sources, 0) is None


def test_a_small_list_losing_a_few_entries_is_not_a_collapse(dirs):
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=lines(40))
    keep(lkg, URL_A, lines(900), NOW - timedelta(days=1))

    apply(sources, lkg, NOW)

    assert fallback_of(sources, 0) is None


def test_a_copy_older_than_seven_days_is_not_used(dirs):
    """A source gone for good must eventually be seen to be gone rather than
    impersonated by an ever older snapshot. Break-test: drop the age check in
    decide() and this fails."""
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=None, status='404')
    keep(lkg, URL_A, lines(5000), NOW - timedelta(days=7, hours=1))

    apply(sources, lkg, NOW)

    assert not (sources / '000.fqdn.list').exists()
    assert fallback_of(sources, 0) is None
    report = json.loads((sources / 'lkg.json').read_text())
    assert report['excluded'][0]['url'] == URL_A


def test_copies_follow_the_url_not_the_position(dirs):
    """The index is a line number in blacklists.fqdn.urls and moves whenever a
    line is added above. The copy must follow the source, not the slot."""
    sources, lkg = dirs
    keep(lkg, URL_A, lines(5000, 'a'), NOW - timedelta(days=1))
    keep(lkg, URL_B, lines(5000, 'b'), NOW - timedelta(days=1))
    write_source(sources, 0, URL_B, body=None, status='503')

    apply(sources, lkg, NOW)

    assert (sources / '000.fqdn.list').read_text() == lines(5000, 'b')


def test_without_kept_copies_nothing_changes(dirs):
    """The state of every local run, and of the first run after this ships."""
    sources, lkg = dirs
    write_source(sources, 0, URL_A, body=lines(10))
    write_source(sources, 1, URL_B, body=None, status='404')

    apply(sources, lkg, NOW)

    assert (sources / '000.fqdn.list').read_text() == lines(10)
    assert not (sources / '001.fqdn.list').exists()
    assert not list(sources.glob('*.fallback'))


def test_a_corrupt_manifest_means_no_fallback_not_a_failed_release(dirs):
    sources, lkg = dirs
    lkg.mkdir()
    (lkg / 'manifest.json').write_text('{not json', encoding='utf-8')
    write_source(sources, 0, URL_A, body=None, status='404')

    assert apply(sources, lkg, NOW) == 0
    assert not (sources / '000.fqdn.list').exists()


# --------------------------------------------------------------------------
# save
# --------------------------------------------------------------------------

def test_save_refreshes_fresh_sources_and_keeps_the_age_of_a_fallback(dirs):
    """Refreshing a copy from a source on its fallback would reset the age
    and let the copy stand in forever. Break-test: drop the .fallback check
    in save() and this fails."""
    sources, lkg = dirs
    saved = NOW - timedelta(days=3)
    keep(lkg, URL_A, lines(5000, 'a'), saved)
    keep(lkg, URL_B, lines(5000, 'b'), saved)
    write_source(sources, 0, URL_A, body=lines(5100, 'a'))
    write_source(sources, 1, URL_B, body=None, status='404')
    apply(sources, lkg, NOW)

    save(sources, lkg, NOW)

    manifest = json.loads((lkg / 'manifest.json').read_text())
    assert manifest[url_key(URL_A)]['saved_at'] == NOW.isoformat()
    assert manifest[url_key(URL_A)]['entries'] == 5100
    assert manifest[url_key(URL_B)]['saved_at'] == saved.isoformat()


def test_save_drops_a_source_that_is_no_longer_configured(dirs):
    sources, lkg = dirs
    keep(lkg, URL_B, lines(10), NOW - timedelta(days=1))
    write_source(sources, 0, URL_A, body=lines(10))

    save(sources, lkg, NOW)

    manifest = json.loads((lkg / 'manifest.json').read_text())
    assert list(manifest) == [url_key(URL_A)]
    assert not (lkg / f'{url_key(URL_B)}.list').exists()


def test_comments_and_markup_do_not_count_as_entries(tmp_path):
    path = tmp_path / 'x.txt'
    path.write_text('# hosts\n! adblock\n[Adblock Plus]\n\n<html>\n'
                    '0.0.0.0 a.example\n||b.example^\nc.example\n', encoding='utf-8')
    assert source_lkg.count_entries(path) == 3


# --------------------------------------------------------------------------
# source_stats.py carries the decision into the published statistics
# --------------------------------------------------------------------------

def test_source_stats_records_which_sources_were_on_fallback(tmp_path, monkeypatch):
    import source_stats

    sources = tmp_path / 'sources_raw'
    write_source(sources, 0, URL_A, body='a.example\n', status='404')
    (sources / '000.fallback').write_text(json.dumps({
        'reason': 'download failed', 'kept_age_days': 2.0}), encoding='utf-8')
    write_source(sources, 1, URL_B, body='b.example\n')
    (tmp_path / 'all.fqdn.blacklist').write_text('a.example\nb.example\n', encoding='utf-8')
    (tmp_path / 'stats').mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(source_stats, 'SOURCES_DIR', source_stats.Path('sources_raw'))
    monkeypatch.setattr(source_stats, 'BLACKLIST', source_stats.Path('all.fqdn.blacklist'))
    monkeypatch.setattr(source_stats, 'REGISTRY', source_stats.Path('none.json'))
    monkeypatch.setattr(source_stats, 'OUTPUT', source_stats.Path('stats/sources.json'))
    assert source_stats.main() == 0

    payload = json.loads((tmp_path / 'stats' / 'sources.json').read_text())
    assert payload['sources_on_fallback'] == 1
    by_url = {s['url']: s for s in payload['sources']}
    assert by_url[URL_A]['fallback']['reason'] == 'download failed'
    assert by_url[URL_B]['fallback'] is None
