"""Tests for scripts/format_whitelist.py.

The normaliser exists because its predecessor deleted 384 whitelist entries: it
validated whole lines against an FQDN regex, so the day entries gained trailing
comments none of them matched and all were dropped - every entry that was
actively holding a source back, a DNS resolver and a CDN apex among them.

The first test below is that failure, written down.
"""

import pytest

from format_whitelist import format_whitelist, is_valid_domain, split_entry


# --------------------------------------------------------------------------
# The regression that motivated this file
# --------------------------------------------------------------------------

def test_an_annotated_entry_is_never_dropped():
    """The exact shape that used to be deleted."""
    text = 'cloudflare-dns.com  # 2026-07-31: blocked by Tracking aggressive extended\n'
    formatted, dropped = format_whitelist(text)

    assert dropped == []
    assert 'cloudflare-dns.com' in formatted
    assert 'blocked by Tracking aggressive extended' in formatted


def test_no_entry_is_lost_when_only_some_are_annotated():
    text = (
        'plain.example\n'
        'annotated.example  # a reason\n'
        'another.example\n'
    )
    formatted, dropped = format_whitelist(text)

    domains = [
        line.split('#')[0].strip()
        for line in formatted.splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]
    assert sorted(domains) == ['annotated.example', 'another.example', 'plain.example']
    assert dropped == []


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def test_entries_are_lowercased_and_sorted():
    formatted, _ = format_whitelist('Zebra.EXAMPLE\nalpha.example\n')
    body = [l for l in formatted.splitlines() if l.strip()]
    assert body == ['alpha.example', 'zebra.example']


def test_duplicates_collapse_and_the_explained_copy_wins():
    """An entry with a reason is worth more than one without."""
    formatted, _ = format_whitelist(
        'dup.example\n'
        'dup.example  # this is why\n'
    )
    body = [l for l in formatted.splitlines() if l.strip()]
    assert body == ['dup.example  # this is why']


def test_the_header_block_is_preserved_verbatim():
    text = (
        '# Domains removed from the published blacklist.\n'
        '#\n'
        '# Format: one domain per line.\n'
        '\n'
        'example.com\n'
    )
    formatted, _ = format_whitelist(text)
    assert formatted.startswith(
        '# Domains removed from the published blacklist.\n'
        '#\n'
        '# Format: one domain per line.\n'
    )
    assert 'example.com' in formatted


def test_output_is_stable_when_run_twice():
    """The workflow reruns on every push; a normaliser that keeps changing the
    file would commit on every run forever."""
    text = '# header\n\nb.example  # note\na.example\n'
    once, _ = format_whitelist(text)
    twice, _ = format_whitelist(once)
    assert once == twice


# --------------------------------------------------------------------------
# Rejection, and saying so
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    'not-a-domain',
    '-leading-hyphen.com',
    'trailing-hyphen-.com',
    'example.123',
    'has space.com',
])
def test_malformed_entries_are_dropped_and_reported(line):
    formatted, dropped = format_whitelist(line + '\n')
    assert line not in formatted
    assert len(dropped) == 1
    assert line in dropped[0]


def test_a_free_standing_comment_is_dropped_and_reported():
    """Sorting would attach it to an unrelated domain, so it cannot be kept."""
    _, dropped = format_whitelist('a.example\n# orphaned note\nb.example\n')
    assert len(dropped) == 1
    assert 'free-standing comment' in dropped[0]


@pytest.mark.parametrize('domain,valid', [
    ('example.com', True),
    ('sub.example.co.uk', True),
    ('xn--80ak6aa92e.com', True),
    ('example', False),
    ('example.1com', False),
    ('', False),
])
def test_is_valid_domain(domain, valid):
    assert is_valid_domain(domain) is valid


@pytest.mark.parametrize('line,expected', [
    ('example.com', ('example.com', None)),
    ('example.com # why', ('example.com', 'why')),
    ('example.com#why', ('example.com', 'why')),
    ('# just a comment', ('', 'just a comment')),
])
def test_split_entry(line, expected):
    assert split_entry(line) == expected
