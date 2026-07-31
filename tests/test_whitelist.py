"""Tests for whitelist.py - the file that holds domains out of the release.

The whitelist gained comments so entries can record why they exist. That is only
safe if the parser strips them: an annotated entry read literally matches no
domain and stops protecting anything, silently, because a whitelist that quietly
does nothing looks exactly like a whitelist with nothing to do.
"""

import pytest

from whitelist import parse_fqdn_line, read_fqdn_from_file


@pytest.mark.parametrize('line,expected', [
    ('example.com', 'example.com'),
    ('example.com  # 2026-07-31: blocked by Some List', 'example.com'),
    ('example.com#terse', 'example.com'),
    ('  example.com  ', 'example.com'),
    ('# a whole-line comment', ''),
    ('', ''),
    ('   ', ''),
])
def test_the_domain_survives_its_comment(line, expected):
    assert parse_fqdn_line(line) == expected


def test_an_annotated_file_yields_the_same_domains_as_a_bare_one(tmp_path):
    """The property that matters: annotating must not disable a single entry."""
    bare = tmp_path / 'bare.txt'
    annotated = tmp_path / 'annotated.txt'

    domains = ['one.example', 'two.example', 'three.example']
    bare.write_text('\n'.join(domains) + '\n', encoding='utf-8')
    annotated.write_text(
        '# header\n'
        '#\n'
        'one.example  # 2026-07-31: blocked by A, B\n'
        'two.example\n'
        'three.example  # hand-written reason\n',
        encoding='utf-8',
    )

    assert read_fqdn_from_file(bare) == read_fqdn_from_file(annotated) == set(domains)


def test_comment_lines_do_not_become_whitelist_entries(tmp_path):
    path = tmp_path / 'wl.txt'
    path.write_text('# not a domain\nreal.example\n', encoding='utf-8')
    assert read_fqdn_from_file(path) == {'real.example'}


def test_filtering_removes_exactly_the_whitelisted_domains(tmp_path):
    """End to end through main(), the way the pipeline invokes it."""
    from whitelist import main

    blacklist = tmp_path / 'bl.txt'
    whitelist = tmp_path / 'wl.txt'
    output = tmp_path / 'out.txt'

    blacklist.write_text('keep.example\ndrop.example\nalso-keep.example\n', encoding='utf-8')
    whitelist.write_text('drop.example  # annotated\n', encoding='utf-8')

    main(blacklist, whitelist, output)

    assert set(output.read_text(encoding='utf-8').split()) == {
        'keep.example', 'also-keep.example'
    }
