"""Tests for scripts/classify_content.py.

Categories are otherwise derived from how each upstream labels itself, which
cannot see a category no source declares. Adult content was blocked extensively
and declared nowhere for exactly that reason, so this classifies by content
against a reference list instead.
"""

import io
import tarfile

import pytest

from classify_content import fetch_reference, load_published


def make_archive(tmp_path, category, domains):
    """Build an archive shaped like a UT1 category download."""
    path = tmp_path / f'{category}.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        payload = ('\n'.join(domains) + '\n').encode('utf-8')
        info = tarfile.TarInfo(f'{category}/domains')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return path


def test_published_header_is_not_read_as_a_domain(tmp_path):
    path = tmp_path / 'bl.txt'
    path.write_text(
        '# Aggregated by fabriziosalmi/blacklists\n'
        'One.example\n'
        'two.example\n',
        encoding='utf-8',
    )
    assert load_published(path) == {'one.example', 'two.example'}


def test_reference_is_read_from_a_cached_archive(tmp_path):
    make_archive(tmp_path, 'adult', ['a.example', 'B.example'])
    assert fetch_reference('adult', tmp_path) == {'a.example', 'b.example'}


def test_reference_ignores_comments(tmp_path):
    make_archive(tmp_path, 'adult', ['# a note', 'real.example'])
    assert fetch_reference('adult', tmp_path) == {'real.example'}


def test_an_archive_without_a_domains_file_is_an_error(tmp_path):
    path = tmp_path / 'adult.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        payload = b'nothing\n'
        info = tarfile.TarInfo('adult/urls')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match='no domains file'):
        fetch_reference('adult', tmp_path)


def test_classification_counts_only_the_overlap(tmp_path):
    """The published figure is the intersection, not the reference size."""
    blacklist = tmp_path / 'bl.txt'
    blacklist.write_text('a.example\nb.example\nc.example\n', encoding='utf-8')
    make_archive(tmp_path, 'adult', ['b.example', 'c.example', 'd.example'])

    published = load_published(blacklist)
    reference = fetch_reference('adult', tmp_path)
    assert len(published & reference) == 2
