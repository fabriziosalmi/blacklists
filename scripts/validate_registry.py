#!/usr/bin/env python3
"""
Validate sources/registry.json against blacklists.fqdn.urls.

The URL list is what the pipeline actually fetches; the registry is what the
site tells users about those fetches. If the two drift apart the site starts
attributing domains to the wrong project, or silently drops a source from the
published attribution - which for GPL/CC-BY-SA upstreams is a licence problem,
not a cosmetic one. This check fails the build on any drift.

Run: python3 scripts/validate_registry.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REGISTRY = Path('sources/registry.json')
URL_LIST = Path('blacklists.fqdn.urls')

REQUIRED_FIELDS = ('id', 'url', 'name', 'project', 'maintainer', 'homepage',
                   'categories', 'license')
REQUIRED_LICENSE_FIELDS = ('spdx', 'name', 'url', 'verified', 'evidence', 'checked_at')

ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]*$')

# Feeds served out of this repository rather than by a third party. They are
# real sources of domains, but they are not independent corroboration, and every
# published count is framed as lists aggregated FROM OTHERS. Counting one of our
# own among them inflates the single number that represents that independence.
SELF_URL_PREFIX = 'https://raw.githubusercontent.com/fabriziosalmi/blacklists/'

# Licences whose content can be incorporated into a GPL-3.0 combined work.
#
# The published blacklist merges and deduplicates every source into one file, so
# it is a combined work and every source must be compatible with the licence the
# aggregate carries. Deciding that per source, from memory, is how a CC BY-NC
# feed eventually gets added by someone who did not know: the reasoning lives in
# LICENSING.md and the enforcement lives here.
#
# An SPDX id outside this set fails the build. That is the point.
GPL3_COMPATIBLE_SPDX = {
    'MIT',
    'Apache-2.0',
    'BSD-2-Clause',
    'BSD-3-Clause',
    'ISC',
    'GPL-3.0-only',
    'GPL-3.0-or-later',
    'LGPL-3.0-only',
    'LGPL-3.0-or-later',
    'MPL-2.0',
    'CC-BY-SA-4.0',
    'CC-BY-4.0',
    'CC0-1.0',
    'Unlicense',
}

COMPATIBILITY_STATES = ('compatible', 'pending')


def load_urls(path: Path) -> list:
    with path.open(encoding='utf-8') as handle:
        return [
            line.strip() for line in handle
            if line.strip() and not line.strip().startswith('#')
        ]


def main() -> int:
    errors = []
    warnings = []

    if not REGISTRY.exists():
        print(f'FAIL: {REGISTRY} not found', file=sys.stderr)
        return 1
    if not URL_LIST.exists():
        print(f'FAIL: {URL_LIST} not found', file=sys.stderr)
        return 1

    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    sources = registry.get('sources', [])
    urls = load_urls(URL_LIST)

    # 1. The fetched list itself must not contain duplicates.
    for url, count in Counter(urls).items():
        if count > 1:
            errors.append(f'{URL_LIST} lists the same URL {count} times: {url}')

    # 2. Registry and URL list must describe exactly the same set of sources.
    registry_urls = [entry.get('url') for entry in sources]
    for url, count in Counter(registry_urls).items():
        if count > 1:
            errors.append(f'registry contains {count} entries for the same URL: {url}')

    missing = [u for u in urls if u not in set(registry_urls)]
    orphaned = [u for u in registry_urls if u not in set(urls)]
    for url in missing:
        errors.append(f'source is fetched but has no registry entry: {url}')
    for url in orphaned:
        errors.append(f'registry entry is not fetched by the pipeline: {url}')

    # 3. Every entry must be structurally complete.
    seen_ids = Counter(entry.get('id') for entry in sources)
    for entry in sources:
        sid = entry.get('id', '<no id>')

        for field in REQUIRED_FIELDS:
            if entry.get(field) in (None, '', []):
                errors.append(f'[{sid}] missing required field: {field}')

        if not ID_PATTERN.match(str(entry.get('id', ''))):
            errors.append(f'[{sid}] id must be lowercase kebab-case')
        if seen_ids[entry.get('id')] > 1:
            errors.append(f'[{sid}] duplicate source id')

        license = entry.get('license') or {}
        for field in REQUIRED_LICENSE_FIELDS:
            if field not in license:
                errors.append(f'[{sid}] license is missing field: {field}')

        # The core honesty rule: a licence may only claim to be verified if it
        # carries the evidence that verified it.
        if license.get('verified'):
            if not license.get('url'):
                errors.append(f'[{sid}] license marked verified but has no evidence URL')
            if not license.get('evidence'):
                errors.append(f'[{sid}] license marked verified but records no evidence type')
        else:
            if license.get('spdx'):
                errors.append(
                    f'[{sid}] license has an SPDX id but is not marked verified - '
                    f'either verify it or clear the SPDX id'
                )
            warnings.append(f'[{sid}] licence unverified: {license.get("name")}')

        if not isinstance(entry.get('categories'), list):
            errors.append(f'[{sid}] categories must be a list')

        # Every source must state how it reaches the licence the aggregate
        # carries, and a "pending" one must say what is still open. Both are
        # required so that an unreviewed source is visible rather than assumed.
        compat = license.get('gpl3_compatibility') or {}
        status = compat.get('status')
        if status not in COMPATIBILITY_STATES:
            errors.append(
                f'[{sid}] license.gpl3_compatibility.status must be one of '
                f'{", ".join(COMPATIBILITY_STATES)}'
            )
        elif not compat.get('rationale'):
            errors.append(f'[{sid}] gpl3_compatibility records no rationale')
        elif status == 'pending':
            warnings.append(f'[{sid}] GPL-3.0 compatibility not settled: '
                            f'{compat["rationale"][:100]}...')

        # The licence actually relied on: a dual-licensed source is only usable
        # once a branch is elected, and an unrecorded election is unauditable.
        effective = license.get('elected') or license.get('spdx')
        if effective and status == 'compatible' and effective not in GPL3_COMPATIBLE_SPDX:
            errors.append(
                f'[{sid}] {effective} is not in the GPL-3.0-compatible set, so it '
                f'cannot be redistributed inside the aggregate. Either drop the '
                f'source or justify it in LICENSING.md and add it to '
                f'GPL3_COMPATIBLE_SPDX.'
            )
        if license.get('elected') and ' OR ' not in str(license.get('spdx') or ''):
            errors.append(f'[{sid}] license.elected is set but the licence is not dual')

        # A feed served out of this repository must say so. Without this the
        # only thing distinguishing it from a third-party list is a URL nobody
        # reads, and it silently counts as independent corroboration - which is
        # exactly how this project came to advertise 46 upstream sources while
        # aggregating 45 and one of its own.
        flag = entry.get('first_party')
        if not isinstance(flag, bool):
            errors.append(f'[{sid}] first_party must be true or false')
        elif str(entry.get('url', '')).startswith(SELF_URL_PREFIX) and not flag:
            errors.append(
                f'[{sid}] is served from this repository but is not marked '
                f'first_party, so it would be counted as an upstream source'
            )

    first_party = [e for e in sources if e.get('first_party')]
    upstream = [e for e in sources if not e.get('first_party')]

    declared = registry.get('source_count')
    if declared is not None and declared != len(sources):
        errors.append(f'source_count says {declared} but registry holds {len(sources)} sources')

    declared_upstream = registry.get('upstream_count')
    if declared_upstream is not None and declared_upstream != len(upstream):
        errors.append(f'upstream_count says {declared_upstream} but '
                      f'{len(upstream)} sources are third-party')

    declared_first = registry.get('first_party_count')
    if declared_first is not None and declared_first != len(first_party):
        errors.append(f'first_party_count says {declared_first} but '
                      f'{len(first_party)} sources are maintained here')

    for warning in warnings:
        print(f'WARN  {warning}')

    if errors:
        print()
        for error in errors:
            print(f'FAIL  {error}', file=sys.stderr)
        print(f'\n{len(errors)} error(s)', file=sys.stderr)
        return 1

    verified = sum(1 for e in sources if (e.get('license') or {}).get('verified'))
    pending = [e['id'] for e in sources
               if ((e.get('license') or {}).get('gpl3_compatibility') or {})
               .get('status') == 'pending']

    print(f'\nOK: {len(sources)} feeds, registry matches {URL_LIST}')
    print(f'    upstream (third-party) : {len(upstream)}')
    print(f'    maintained here        : {len(first_party)}'
          + (f"  ({', '.join(e['id'] for e in first_party)})" if first_party else ''))
    print(f'    licences verified      : {verified}/{len(sources)}')
    print(f'    aggregate licence      : {registry.get("aggregate_license") or "NOT DECLARED"}')
    print(f'    GPL-3.0 compatibility  : {len(sources) - len(pending)}/{len(sources)} settled'
          + (f'   pending: {", ".join(pending)}' if pending else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
