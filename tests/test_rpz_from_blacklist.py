"""Tests for rpz_from_blacklist.py, the step that decides what reaches the zone.

The case that matters here reached a published release: for months the RPZ was
emitted by a bare awk with no SOA, no NS and no verification, so the artifact was
never a loadable zone. When the verification was finally added on 2026-09-10 it
failed immediately, on a single 249-character entry out of six million.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from rpz_from_blacklist import MAX_ENCODED_NAME, build, encoded_length, fits, main

ORIGIN = 'rpz.blacklist'


def test_encoded_length_counts_a_byte_per_label_plus_the_root():
    # "a.b" under origin "x" -> labels a,b,x = (1+1)+(1+1)+(1+1) + 1 root
    assert encoded_length('a.b', 'x') == 7


def test_the_entry_that_broke_the_release_does_not_fit():
    entry = ('https.outlook.live.com.user0500.deor.error.'
             'c8nkichfistk8dphfvkfd9ssli82.is38avdj8h0k381gx0id7hhkg8l.'
             '6dls9sz6hv72290ddkuhs.7lxhhjh86k0f2hrivsb1jku718.'
             '7lxhhjh86k0f2hrivsb1jku718.h7g6fi9d0fhy6kk6htk4.'
             'kwddz0mtsqe28sh3wkj9nhhsd6drh.linestarts.duckdns.org')
    assert len(entry) == 249
    assert encoded_length(entry, ORIGIN) == 265      # measured against named-checkzone
    assert not fits(entry, ORIGIN)


def test_the_boundary_is_the_encoded_limit_not_the_character_count():
    """255 octets passes, 256 does not, whatever the label count.

    Both of these were confirmed against named-checkzone 9.20.27: the number of
    labels does not move the boundary, so a filter written on len(entry) alone is
    wrong for any other origin.
    """
    for labels in (8, 17):
        budget = MAX_ENCODED_NAME - encoded_length('', ORIGIN) - labels
        base, extra = divmod(budget, labels)
        name = '.'.join('a' * (base + (1 if i < extra else 0)) for i in range(labels))
        assert encoded_length(name, ORIGIN) == MAX_ENCODED_NAME
        assert fits(name, ORIGIN)
        assert not fits(name + 'a', ORIGIN)


def test_a_short_name_under_a_long_origin_can_still_overflow():
    """The origin is part of the name, so the same entry can fit in one zone and
    not in another. A filter that ignores the origin is wrong."""
    entry = 'a' * 200
    assert fits(entry, 'x')
    assert not fits(entry, 'a' * 60)


def test_build_keeps_the_good_and_reports_the_bad(tmp_path):
    src = tmp_path / 'blacklist.txt'
    src.write_text('# header, dropped\n\nexample.com\n' + 'b' * 250 + '.com\nok.example\n')
    out = tmp_path / 'z.txt'
    kept, dropped = build(src, out, ORIGIN, '1')
    assert kept == 2
    assert len(dropped) == 1 and dropped[0].startswith('bbb')
    body = out.read_text()
    assert 'example.com CNAME .' in body
    assert 'IN SOA' in body and 'IN NS' in body      # a zone, not a bare record list
    assert '# header' not in body                    # BIND comments with ';'


def test_too_many_dropped_fails_instead_of_silently_thinning_the_list(tmp_path):
    """One bad row is an upstream typo. Hundreds is a format change, and
    discarding real blocking rules quietly is worse than not shipping."""
    src = tmp_path / 'blacklist.txt'
    src.write_text('\n'.join(f'{"c" * 250}.{i}.com' for i in range(30)) + '\n')
    out = tmp_path / 'z.txt'
    rc = main(['--blacklist', str(src), '--out', str(out), '--max-dropped', '25'])
    assert rc == 1


def test_missing_input_fails(tmp_path):
    assert main(['--blacklist', str(tmp_path / 'nope.txt'), '--out', str(tmp_path / 'z')]) == 1
