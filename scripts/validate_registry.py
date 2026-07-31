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

    declared = registry.get('source_count')
    if declared is not None and declared != len(sources):
        errors.append(f'source_count says {declared} but registry holds {len(sources)} sources')

    for warning in warnings:
        print(f'WARN  {warning}')

    if errors:
        print()
        for error in errors:
            print(f'FAIL  {error}', file=sys.stderr)
        print(f'\n{len(errors)} error(s)', file=sys.stderr)
        return 1

    verified = sum(1 for e in sources if (e.get('license') or {}).get('verified'))
    print(f'\nOK: {len(sources)} sources, registry matches {URL_LIST}')
    print(f'    licences verified: {verified}/{len(sources)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
