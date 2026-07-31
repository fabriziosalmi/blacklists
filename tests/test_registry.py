"""Tests for the source registry and the documents generated from it.

These assert the invariants the project relies on rather than the current
contents: the registry describes exactly what the pipeline fetches, and every
licence claim carries the evidence that supports it. Redistributing an
aggregated list without accurate attribution is a licensing problem, so these
are correctness tests, not documentation tests.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / 'sources' / 'registry.json'
URL_LIST_PATH = REPO_ROOT / 'blacklists.fqdn.urls'


@pytest.fixture(scope='module')
def registry():
    return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def fetched_urls():
    with URL_LIST_PATH.open(encoding='utf-8') as handle:
        return [
            line.strip() for line in handle
            if line.strip() and not line.strip().startswith('#')
        ]


def test_registry_describes_exactly_what_is_fetched(registry, fetched_urls):
    assert sorted(e['url'] for e in registry['sources']) == sorted(fetched_urls)


def test_no_url_is_fetched_twice(fetched_urls):
    """A duplicate inflates the source count without adding a single domain."""
    assert len(set(fetched_urls)) == len(fetched_urls)


def test_source_ids_are_unique(registry):
    ids = [e['id'] for e in registry['sources']]
    assert len(set(ids)) == len(ids)


def test_declared_source_count_matches(registry):
    assert registry['source_count'] == len(registry['sources'])


@pytest.mark.parametrize('field', [
    'id', 'url', 'name', 'project', 'maintainer', 'homepage', 'categories', 'license',
])
def test_every_source_is_fully_described(registry, field):
    missing = [e.get('id', '?') for e in registry['sources'] if not e.get(field)]
    assert not missing, f'sources missing {field}: {missing}'


def test_a_verified_licence_carries_its_evidence(registry):
    """"Verified" must mean someone can re-check it, not that someone believed it."""
    bad = [
        e['id'] for e in registry['sources']
        if e['license'].get('verified')
        and not (e['license'].get('url') and e['license'].get('evidence'))
    ]
    assert not bad, f'verified licence without evidence: {bad}'


def test_an_unverified_licence_makes_no_spdx_claim(registry):
    """An SPDX identifier is a specific legal claim; it cannot be a guess."""
    bad = [
        e['id'] for e in registry['sources']
        if not e['license'].get('verified') and e['license'].get('spdx')
    ]
    assert not bad, f'unverified licence asserting an SPDX id: {bad}'


def test_removed_sources_record_why(registry):
    for entry in registry.get('removed_sources', []):
        assert entry.get('reason'), f'removed source without a reason: {entry.get("name")}'
        assert entry.get('detail'), f'removed source without detail: {entry.get("name")}'


def test_generated_documents_are_current():
    """SOURCES.md and the README credits are generated; drift means the
    published attribution no longer matches what is fetched."""
    import subprocess

    result = subprocess.run(
        ['python3', 'scripts/generate_sources_md.py', '--check'],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_registry_matches_url_list_per_the_validator():
    """The same check the release workflow runs before doing any work."""
    import subprocess

    result = subprocess.run(
        ['python3', 'scripts/validate_registry.py'],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
