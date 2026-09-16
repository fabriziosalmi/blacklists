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
    MAX_ENCODED_NAME,
    drop_metadata,
    encoded_length,
    fits,
    is_valid_fqdn,
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
# Cosmetic filters
#
# These are anchored to a BARE domain, with no "||" prefix. That is the whole
# difficulty: strip_adblock_syntax only inspects lines starting with "||", so a
# cosmetic rule walked past every guard and reached take_first_token, which
# split it on "#" and kept the hostname.
#
# The case above pinned '||example.com##.ad-banner' - a form that does not occur
# in the wild, because the "||" prefix is what makes it a network rule. The
# tests here use the shape sources actually publish, which shipped
# pages.dev, web.core.windows.net, webflow.io, ondigitalocean.app and
# ublockorigin.com to users.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    'example.com##.ad-banner',                 # element hiding
    'example.com##+js(aeld, mousemove, x)',    # scriptlet injection (uBO)
    'example.com#@#.ad-banner',                # element hiding EXCEPTION
    'example.com#?#div:has-text(Offer)',       # extended CSS selector
    'example.com#$#.banner { display: none }', # style injection
    'example.com#%#//scriptlet("abort")',      # AdGuard scriptlet
    'example.com#@$#.banner { color: red }',   # negated style injection
    'example.com###promo-box',                 # id selector, "##" + "#promo-box"
    'example.com##main::before:style(content: "x")',
])
def test_cosmetic_rules_never_become_domain_blocks(line, rules):
    """A cosmetic rule says "load this site and hide an element on it".

    Reading it as a block inverts the author's intent exactly as an "@@"
    exception would.
    """
    assert sanitize(line, rules) is None


@pytest.mark.parametrize('line', [
    'pages.dev##html[lang="ja"] > body > .main-container',
    'web.core.windows.net##+js(aeld, beforeunload, /[Ww]orker/)',
    'webflow.io##html.w-mod-js:not(.wf-active) > body:not([class])',
    'ondigitalocean.app##+js(aeld, mousemove, loadSecret)',
    'ublockorigin.com##.title::before:style(content: "not official")',
])
def test_shared_hosting_apexes_are_not_blocked_by_cosmetic_rules(line, rules):
    """The regression that put hosting apexes in the published list.

    Each of these blocked every unrelated site under the apex, and the Unbound
    and RPZ outputs expand a listed name to its whole subtree. None of the four
    quality gates could see it: the size gate only measures shrinkage, and
    sources/protected.txt is a hand-curated list that did not name them.
    """
    assert sanitize(line, rules) is None


def test_multi_domain_cosmetic_rules_are_dropped(rules):
    """One rule can carry several hostnames and a negation."""
    assert sanitize('~support.ublock.org,ublock.org##main::before', rules) is None
    assert sanitize('a.example,b.example##.ad', rules) is None


def test_inline_comment_is_still_a_comment_not_a_cosmetic_rule(rules):
    """The separator is only cosmetic when attached to the hostname.

    Whitespace before it means a human wrote a note, so these must survive.
    """
    assert sanitize('example.com  ## why this is listed', rules) == 'example.com'
    assert sanitize('example.com # note ## more', rules) == 'example.com'
    assert sanitize('0.0.0.0 example.com  # see #123', rules) == 'example.com'


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


# --------------------------------------------------------------------------
# Name length
#
# is_valid_fqdn checked each label against a pattern and never measured the
# name as a whole, so it accepted names no resolver can put on the wire. One
# such entry - 249 characters, every label fine - entered the published list
# and then made named-checkzone refuse the ENTIRE RPZ zone once the origin
# pushed it past 255 octets. Six million domains did not ship because of one
# upstream row.
# --------------------------------------------------------------------------

def test_encoded_length_is_not_the_character_count():
    """One length byte per label, plus the labels, plus the root."""
    assert encoded_length('a.b') == 1 + 1 + 1 + 1 + 1        # a=2, b=2, root=1
    assert encoded_length('a.b', 'x') == 7
    # For a bare name the octet count is the character count plus two.
    assert encoded_length('example.com') == len('example.com') + 2


def test_a_name_whose_labels_are_all_valid_can_still_be_too_long():
    """The hole this closes: per-label checks say nothing about the total."""
    name = '.'.join(['a' * 50] * 6) + '.com'
    assert len(name) == 309
    assert all(len(label) <= 63 for label in name.split('.'))
    assert not fits(name)
    assert not is_valid_fqdn(name)


def test_the_boundary_is_the_encoded_limit():
    """Built to land exactly on 255 octets, so one more character must fail.

    encoded = sum(len(label)) + one length byte per label + the root byte, so
    the label characters available are MAX - labels - 1. Dividing that evenly
    leaves a remainder, and ignoring it lands short of the boundary rather than
    on it - which is a test that passes without testing anything.
    """
    labels = 4
    budget = MAX_ENCODED_NAME - labels - 1
    sizes = [budget // labels] * labels
    for i in range(budget - sum(sizes)):
        sizes[i] += 1
    assert sum(sizes) == budget and all(size <= 63 for size in sizes)

    name = '.'.join('a' * size for size in sizes)
    assert encoded_length(name) == MAX_ENCODED_NAME
    assert fits(name)
    assert not fits(name + 'a')


def test_an_ordinary_domain_is_unaffected():
    for name in ('example.com', 'sub.example.co.uk', 'a.b.c.example.org'):
        assert fits(name)
        assert is_valid_fqdn(name)


def test_the_entry_that_stopped_the_release_is_now_rejected_at_the_source():
    """249 characters, 17 labels: valid alone, 265 octets under rpz.blacklist.

    It is under the 255-octet limit as a bare name, so is_valid_fqdn keeps it -
    correctly, because it IS resolvable on its own. The RPZ builder is what
    measures it against the origin. This pins the division of labour: the
    source check rejects the unresolvable, the zone builder rejects what does
    not fit in the zone.
    """
    entry = '.'.join(['aaaaaaaaaaaaaa'] * 16) + '.org'
    assert len(entry) == 243
    assert fits(entry)                    # resolvable on its own
    assert not fits(entry, 'rpz.blacklist')   # but not as an owner name there
