"""Tests for sanitize.py - the code that decides what ends up blocked.

Every case here corresponds to a bug that reached (or nearly reached) a
published release. They are written as executable statements of intent so the
next person to touch the parser finds out immediately if they invert one.

`is_valid_fqdn` calls tldextract, which downloads a public-suffix snapshot on
first use. These tests exercise the rules directly and only reach for
`is_valid_fqdn` where the case is specifically about validity, so the suite runs
offline.
"""

import pytest

from sanitize import (
    drop_metadata,
    get_sanitization_rules,
    remove_prefixes,
    sanitize_line,
    strip_adblock_syntax,
    take_first_token,
)


@pytest.fixture(scope='module')
def rules():
    return get_sanitization_rules()


def sanitize(line, rules):
    """Run one raw line through the full rule chain."""
    return sanitize_line(line, rules)


# --------------------------------------------------------------------------
# Adblock syntax
#
# The pipeline ignored these lists entirely until the "^" terminator was
# handled, and then over-blocked until "$" modifiers were handled. Both
# directions are pinned here.
# --------------------------------------------------------------------------

def test_plain_domain_anchor_is_translated(rules):
    assert sanitize('||example.com^', rules) == 'example.com'


def test_domain_anchor_without_terminator_is_translated(rules):
    assert sanitize('||example.com', rules) == 'example.com'


@pytest.mark.parametrize('line', [
    '||example.com^$doc',                      # browser warning, not a block
    '||example.com^$all,badfilter',            # cancels another rule
    '||example.com.$all,to=~cloudflare.net',   # conditional on destination
    '||example.com^$third-party',
    '||example.com^$script',
    '||example.com$removeparam=x',
])
def test_modifier_rules_are_dropped(line, rules):
    """A "$" modifier makes a rule conditional or cancels it outright.

    Blocking on any of them asserts something the upstream author did not.
    badfilter in particular means the exact opposite of a block.
    """
    assert sanitize(line, rules) is None


def test_modifier_check_precedes_terminator_split():
    """The hostname does not always end with "^" before "$".

    ||example.com.$all ends it with a dot, so a parser that splits on "^" first
    never sees the modifier. This is how roblox.com became blocked.
    """
    assert strip_adblock_syntax('||example.com.$all,to=~x') is None


def test_exception_rules_are_dropped(rules):
    """"@@" marks entries the upstream author decided must NOT be blocked."""
    assert sanitize('@@||example.com^', rules) is None
    assert sanitize('@@||example.com^$document', rules) is None


@pytest.mark.parametrize('line', [
    '||example.com/path/to/thing',   # scopes to a URL, not a host
    '||example.com/',
    '||ex*mple.com^',                # wildcard has no domain-list equivalent
    '||example.com##.ad-banner',     # element hiding
])
def test_untranslatable_rules_are_dropped(line, rules):
    assert sanitize(line, rules) is None


# --------------------------------------------------------------------------
# Metadata and comments
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    '[Adblock Plus]',
    '[Adblock Plus 2.0]',
    '! Title: Some List',
    '# Comment',
    '',
    '   ',
])
def test_metadata_lines_are_dropped(line, rules):
    assert sanitize(line, rules) is None


def test_drop_metadata_passes_real_entries_through():
    assert drop_metadata('example.com') == 'example.com'


# --------------------------------------------------------------------------
# hosts files and trailing text
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line,expected', [
    ('0.0.0.0 example.com', 'example.com'),
    ('127.0.0.1 example.com', 'example.com'),
    ('0.0.0.0\texample.com', 'example.com'),
    ('0.0.0.0 example.com # a note', 'example.com'),
    ('example.com #tracker', 'example.com'),
    ('example.com !tracker', 'example.com'),
])
def test_hosts_and_trailing_comments(line, expected, rules):
    """notrack publishes "domain #comment"; hosts files put the address first.

    Neither was handled before, and notrack contributed nothing as a result.
    """
    assert sanitize(line, rules) == expected


def test_url_prefixes_are_stripped(rules):
    assert sanitize('https://example.com', rules) == 'example.com'
    assert sanitize('http://example.com', rules) == 'example.com'


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def test_case_and_trailing_dot_are_normalised(rules):
    assert sanitize('Example.COM.', rules) == 'example.com'


def test_remove_prefixes_only_strips_a_leading_match():
    assert remove_prefixes('example.com', ['0.0.0.0']) == 'example.com'
    assert remove_prefixes('0.0.0.0 example.com', ['0.0.0.0']) == 'example.com'


def test_take_first_token_returns_none_for_empty_input():
    assert take_first_token('') is None
    assert take_first_token('   ') is None


# --------------------------------------------------------------------------
# Whole-file behaviour
# --------------------------------------------------------------------------

def test_adblock_list_yields_only_unconditional_rules(rules):
    """An excerpt in the shape real sources publish."""
    document = [
        '[Adblock Plus 2.0]',
        '! Title: Example list',
        '||blocked-one.com^',
        '||blocked-two.com^',
        '||warned.com^$doc',
        '@@||allowed.com^',
        '||cancelled.com^$all,badfilter',
        '||scoped.com/ads/',
    ]
    got = [d for d in (sanitize(line, rules) for line in document) if d]
    assert got == ['blocked-one.com', 'blocked-two.com']
