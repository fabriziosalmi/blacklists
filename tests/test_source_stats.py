"""Tests for scripts/source_stats.py - per-source attribution.

Two normalisations live here and they must stay different. `supplier_normalize`
answers "what did this source mean to list", `pipeline_normalize` answers "what
can sanitize.py actually read". Their disagreement is the signal that a source
is being fetched and silently ignored - the condition that left eleven sources
contributing nothing.
"""

import pytest

from source_stats import (
    detect_format,
    pipeline_normalize,
    supplier_normalize,
)


# --------------------------------------------------------------------------
# supplier_normalize: lenient, used to credit a source for a published domain
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line,expected', [
    ('example.com', 'example.com'),
    ('0.0.0.0 example.com', 'example.com'),
    ('127.0.0.1\texample.com', 'example.com'),
    ('example.com #tracker', 'example.com'),
    ('||example.com^', 'example.com'),
    ('||example.com^$doc', 'example.com'),
    ('https://example.com', 'example.com'),
    ('Example.COM.', 'example.com'),
])
def test_supplier_normalize_understands_every_published_shape(line, expected):
    assert supplier_normalize(line) == expected


@pytest.mark.parametrize('line', [
    '! comment', '# comment', '[Adblock Plus]', '', '   ',
    '||*.example.com^',   # wildcard names no single domain
    'not-a-domain',       # no dot, cannot be an FQDN
])
def test_supplier_normalize_rejects_non_domains(line):
    assert supplier_normalize(line) is None


def test_supplier_normalize_keeps_the_host_from_a_url_with_a_path():
    """Attribution is about which source named the host, so a path is dropped
    rather than the whole line - unlike the pipeline, which refuses the rule."""
    assert supplier_normalize('https://example.com/some/path') == 'example.com'


# --------------------------------------------------------------------------
# pipeline_normalize: strict, mirrors sanitize.py
# --------------------------------------------------------------------------

@pytest.mark.parametrize('line,expected', [
    ('example.com', 'example.com'),
    ('0.0.0.0 example.com', 'example.com'),
    ('||example.com^', 'example.com'),
])
def test_pipeline_normalize_accepts_what_sanitize_accepts(line, expected):
    assert pipeline_normalize(line) == expected


@pytest.mark.parametrize('line', [
    '||example.com^$doc',
    '||example.com^$all,badfilter',
    '||example.com.$all,to=~x',
    '@@||example.com^',
    '||example.com/path',
    '# comment',
    '! comment',
    '[Adblock Plus]',
])
def test_pipeline_normalize_rejects_what_sanitize_rejects(line):
    assert pipeline_normalize(line) is None


def test_the_two_normalisations_disagree_on_modifier_rules():
    """This disagreement is what flags a source as unreadable by the pipeline.

    A source publishing only modifier rules offers domains that never arrive.
    """
    line = '||example.com^$doc'
    assert supplier_normalize(line) == 'example.com'
    assert pipeline_normalize(line) is None


def test_the_two_normalisations_agree_on_a_plain_hosts_entry():
    """No disagreement means the source is being read as its author intended."""
    line = '0.0.0.0 example.com'
    assert supplier_normalize(line) == pipeline_normalize(line) == 'example.com'


# --------------------------------------------------------------------------
# detect_format: classify what a source actually served
# --------------------------------------------------------------------------

@pytest.mark.parametrize('sample,expected', [
    (['[Adblock Plus]', '! Title: x', '||a.com^'], 'adblock'),
    (['! Title: x', '||a.com^'], 'adblock'),
    (['0.0.0.0 a.com', '0.0.0.0 b.com'], 'hosts'),
    (['a.com', 'b.com'], 'domains'),
    (['https://a.com/x', 'https://b.com'], 'url'),
    (['<!DOCTYPE html>', '<html>'], 'html'),
    (['{', '  "a": 1'], 'json'),
    ([], 'empty'),
    (['# only comments'], 'empty'),
])
def test_detect_format(sample, expected):
    assert detect_format(sample) == expected


def test_html_is_detected_even_behind_a_200():
    """A source returning an error page can still answer 200, so the status code
    alone cannot be trusted; the body has to be looked at.

    This is how a GitHub blob page was fed to the aggregator as if it were a
    host list.
    """
    body = ['<!doctype html>', '<html><head><title>404</title></head>']
    assert detect_format(body) == 'html'
