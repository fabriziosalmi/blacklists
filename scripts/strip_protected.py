#!/usr/bin/env python3
"""
Remove from the aggregate every entry that would break a protected name.

Runs inside generate.sh, after whitelisting and before the attribution header
is written, so the domain count in that header is the count that ships:

    python3 scripts/strip_protected.py --blacklist all.fqdn.blacklist

Why the pipeline strips instead of the gate refusing:

From 2026-09-18 to 2026-10-22 the daily release failed on 27 nights because
four protected names - akamai.net, azureedge.net, azurewebsites.net and
cloudfront.net - reached the list. All four came from Adblock rules that carry
a path after the separator (``||akamai.net^/beacon``), which the parser read as
a block on the whole domain. The gate refused, correctly, and the published list
froze. Every night it stayed frozen made the size check against it harder to
pass, so the gate went on failing for a second reason once the first was gone.

Refusing the release protected nobody. The previous list stayed out there,
older every day, and the four names were safe in it only because it predated
the bug. Removing the entries that break a protected name produces exactly the
list a maintainer would have shipped after reading the failure, without anyone
having to read it first.

The gate in scripts/check_quality.py still fails on any protected violation. It
is the second line now: it fires only if this step did not run or missed one,
and a test holds it to that.

What gets removed is the BLOCKER, which is not always the protected name. A
block on digicert.com breaks ocsp.digicert.com on Unbound and AdGuard Home, so
every ancestor of a protected name that appears on the list goes, not only the
closest one: removing ocsp.digicert.com while digicert.com stays would leave
the protected name exactly as broken as before.

Output: the list is rewritten in place, and what was removed, why and which
source supplied it goes to sources_raw/protected_stripped.json, which the gate
copies into stats/quality.json
and the review queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_quality import (  # noqa: E402
    PROTECTED,
    REGISTRY,
    ancestors,
    attribute,
    read_domain_list,
)

OUTPUT_NAME = 'protected_stripped.json'


def blockers_for(protected: Dict[str, Optional[str]]) -> Dict[str, List[str]]:
    """Every name whose presence on the list breaks a protected name.

    Maps each such name to the protected names it breaks. A protected name is
    its own blocker; so is each of its ancestors down to the registered domain.
    """
    blockers: Dict[str, List[str]] = {}
    for domain in sorted(protected):
        for candidate in ancestors(domain):
            blockers.setdefault(candidate, []).append(domain)
    return blockers


def strip(blacklist: Path, blockers: Dict[str, List[str]]) -> List[str]:
    """Rewrite ``blacklist`` without any blocker. Returns the names removed.

    Streams the file: the list is millions of lines and the blocker set is a
    few hundred, so there is no reason to hold the list in memory.
    """
    removed: List[str] = []
    tmp = blacklist.with_name(blacklist.name + '.strip.tmp')
    with blacklist.open(encoding='utf-8', errors='ignore') as src, \
            tmp.open('w', encoding='utf-8') as dst:
        for line in src:
            name = line.strip().lower()
            if name in blockers:
                removed.append(name)
                continue
            dst.write(line)
    tmp.replace(blacklist)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[1])
    parser.add_argument('--blacklist', default='all.fqdn.blacklist', type=Path)
    parser.add_argument('--sources-dir', default='sources_raw', type=Path)
    args = parser.parse_args()

    if not args.blacklist.is_file():
        print(f'FAIL: {args.blacklist} not found', file=sys.stderr)
        return 1

    protected = read_domain_list(PROTECTED)
    if not protected:
        # An empty or missing protected list would turn this step into a no-op
        # that looks like a clean night. Better to stop and say so.
        print(f'FAIL: {PROTECTED} is empty or missing', file=sys.stderr)
        return 1

    blockers = blockers_for(protected)
    removed = strip(args.blacklist, blockers)

    attribution = attribute(set(removed), args.sources_dir, REGISTRY) if removed else {}
    entries = [
        {
            'removed': name,
            'protects': blockers[name],
            'reason': protected.get(blockers[name][0]),
            'sources': attribution.get(name, []),
        }
        for name in sorted(removed)
    ]

    args.sources_dir.mkdir(exist_ok=True)
    (args.sources_dir / OUTPUT_NAME).write_text(json.dumps({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'protected_checked': len(protected),
        'stripped': entries,
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    if not entries:
        print(f'✓ No entry breaks any of the {len(protected)} protected names')
        return 0

    print(f'! Removed {len(entries)} entr{"y" if len(entries) == 1 else "ies"} '
          f'that would break a protected name:')
    for entry in entries:
        who = ', '.join(entry['sources']) or 'source unrecorded'
        print(f'  - {entry["removed"]}  protects {", ".join(entry["protects"])}  '
              f'<- {who}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
