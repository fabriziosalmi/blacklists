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


# --------------------------------------------------------------------------
# First-party feeds
#
# One of the fetched feeds is custom/streaming.txt, maintained in this very
# repository and pulled from GitHub's CDN like any third party. It is a real
# source of domains but it is not independent corroboration, and every published
# figure is framed as lists aggregated FROM OTHERS - so counting it among them
# overstated the number of independent curators by one. These pin the split so
# it cannot quietly close again.
# --------------------------------------------------------------------------

SELF_PREFIX = 'https://raw.githubusercontent.com/fabriziosalmi/blacklists/'


def test_every_entry_declares_whether_it_is_first_party(registry):
    for entry in registry['sources']:
        assert isinstance(entry.get('first_party'), bool), entry['id']


def test_a_feed_served_from_this_repository_is_marked_first_party(registry):
    """The invariant that stops the count silently re-inflating.

    Adding another list of our own to blacklists.fqdn.urls without the flag
    would put it straight back into the upstream total, and the only thing
    distinguishing it would be a URL nobody reads.
    """
    for entry in registry['sources']:
        if entry['url'].startswith(SELF_PREFIX):
            assert entry['first_party'] is True, entry['id']


def test_declared_upstream_and_first_party_counts_match(registry):
    sources = registry['sources']
    upstream = [e for e in sources if not e['first_party']]
    own = [e for e in sources if e['first_party']]

    assert registry['upstream_count'] == len(upstream)
    assert registry['first_party_count'] == len(own)
    assert registry['upstream_count'] + registry['first_party_count'] == len(sources)


def test_the_readme_credits_do_not_thank_this_project(registry):
    """The credits block is introduced as the projects this one depends on.

    Listing ourselves there is not a rounding error in a count, it is thanking
    yourself in a list of other people.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from generate_sources_md import build_credits

    credits = build_credits(registry)
    for entry in registry['sources']:
        if entry['first_party']:
            assert entry['project'] not in credits


# --------------------------------------------------------------------------
# Licence compatibility of the aggregate
#
# The published list is a combined work: sources are merged and deduplicated
# into one file from which none can be extracted, so every input must be
# compatible with the licence the whole carries. Deciding that per source from
# memory is how a non-commercial feed eventually gets added by someone who did
# not know - these make the rule structural.
# --------------------------------------------------------------------------

def test_the_aggregate_declares_a_licence(registry):
    assert registry.get('aggregate_license') == 'GPL-3.0-only'


def test_every_source_states_how_it_reaches_that_licence(registry):
    for entry in registry['sources']:
        compat = entry['license'].get('gpl3_compatibility') or {}
        assert compat.get('status') in ('compatible', 'pending'), entry['id']
        assert compat.get('rationale'), entry['id']


def test_no_settled_source_falls_outside_the_compatible_set(registry):
    """The check that would have caught a CC BY-NC source being added."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from validate_registry import GPL3_COMPATIBLE_SPDX

    for entry in registry['sources']:
        license = entry['license']
        if (license.get('gpl3_compatibility') or {}).get('status') != 'compatible':
            continue
        effective = license.get('elected') or license.get('spdx')
        assert effective in GPL3_COMPATIBLE_SPDX, f"{entry['id']}: {effective}"


def test_a_dual_licensed_source_records_which_branch_is_elected(registry):
    """An unrecorded election cannot be audited by anyone reading the registry."""
    for entry in registry['sources']:
        spdx = entry['license'].get('spdx') or ''
        if ' OR ' in spdx:
            assert entry['license'].get('elected'), entry['id']
            assert entry['license']['elected'] in spdx


def test_non_commercial_licences_are_rejected_outright():
    """The clauses that got five feeds removed must not be quietly re-addable."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from validate_registry import GPL3_COMPATIBLE_SPDX

    for spdx in ('CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0', 'CC-BY-NC-ND-4.0', 'CC-BY-ND-4.0'):
        assert spdx not in GPL3_COMPATIBLE_SPDX


def test_the_published_source_count_excludes_our_own_lists():
    """The headline figure, as generate_stats.py computes it for the README."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from generate_stats import StatsGenerator

    registry = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    counted = StatsGenerator(str(REPO_ROOT)).count_blacklist_sources()

    assert counted == registry['upstream_count']
    assert counted < len(registry['sources'])


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
