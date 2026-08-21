#!/usr/bin/env python3
"""
Measure what the published list blocks by content, not by who supplied it.

stats/sources.json already reports categories, but it derives them from how each
upstream labels itself. That misses anything a source blocks without saying so.
Adult content is the case in point: the list blocks pornhub.com, xvideos.com,
xnxx.com, onlyfans.com and several hundred xhamster mirrors, and not one of the
forty-six sources calls itself an adult blocklist. The category was invisible to
a source-derived count and therefore undeclared on the site for as long as the
site has existed.

This script closes that gap by classifying the published domains against a
reference list instead. The reference is the Universite Toulouse 1 Capitole
blacklist, maintained by a university, updated daily, and already the upstream
for three of this project's sources.

The reference is downloaded during the run and never redistributed - only counts
are published - so it places no licensing obligation on this repository beyond
the credit UT1 is owed either way.

Output: stats/classification.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

UT1_URL = 'https://dsi.ut-capitole.fr/blacklists/download/{category}.tar.gz'

# Categories to classify against. Each must exist as a UT1 archive containing a
# "domains" file. Kept deliberately short: every entry costs a download, and an
# unmeasured category is worse than an absent one.
CATEGORIES = ('adult',)

OUTPUT = Path('stats/classification.json')


def log(message: str) -> None:
    print(message, flush=True)


def load_published(path: Path) -> Set[str]:
    domains = set()
    with path.open(encoding='utf-8', errors='ignore') as handle:
        for line in handle:
            line = line.strip().lower()
            if line and not line.startswith('#'):
                domains.add(line)
    return domains


def fetch_reference(category: str, cache_dir: Optional[Path]) -> Set[str]:
    """Download one UT1 category and return its domains."""
    cached = (cache_dir / f'{category}.tar.gz') if cache_dir else None

    if cached and cached.exists():
        log(f'  using cached {cached}')
        payload = cached.read_bytes()
    else:
        url = UT1_URL.format(category=category)
        log(f'  downloading {url}')
        request = urllib.request.Request(
            url, headers={'User-Agent': 'fabriziosalmi-blacklists/1.0'}
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(payload)

    domains: Set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        member = next(
            (m for m in archive.getmembers()
             if m.isfile() and m.name.endswith('/domains')),
            None,
        )
        if member is None:
            raise ValueError(f'no domains file in the {category} archive')
        handle = archive.extractfile(member)
        for line in handle:
            entry = line.decode('utf-8', 'ignore').strip().lower()
            if entry and not entry.startswith('#'):
                domains.add(entry)

    return domains


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify published domains by content')
    parser.add_argument('--blacklist', default='all.fqdn.blacklist')
    parser.add_argument('--cache-dir', default=None,
                        help='Directory to cache the reference archives in')
    args = parser.parse_args()

    path = Path(args.blacklist)
    if not path.is_file():
        print(f'FAIL: {path} not found', file=sys.stderr)
        return 1

    published = load_published(path)
    log(f'✓ Published domains: {len(published):,}')

    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    results: List[Dict] = []

    for category in CATEGORIES:
        log(f'Classifying against UT1 "{category}"...')
        try:
            reference = fetch_reference(category, cache_dir)
        except Exception as exc:
            # Reporting only: a reference being unreachable says nothing about
            # the list, and must not stop it from shipping.
            log(f'  warning: could not classify {category} ({exc})')
            continue

        matched = published & reference
        results.append({
            'category': category,
            'domains': len(matched),
            'percent': round(len(matched) / len(published) * 100, 2) if published else 0,
            'reference_size': len(reference),
        })
        log(f'  {len(matched):,} of {len(published):,} published domains '
            f'({results[-1]["percent"]}%)')

    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'published_domains': len(published),
        'reference': {
            'name': 'Universite Toulouse 1 Capitole blacklists',
            'url': 'https://dsi.ut-capitole.fr/blacklists/index_en.php',
            'license': 'CC-BY-SA-4.0',
            'note': 'Downloaded at build time to classify, never redistributed.',
        },
        'categories': results,
    }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
                      encoding='utf-8')
    log(f'✓ Wrote {OUTPUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
