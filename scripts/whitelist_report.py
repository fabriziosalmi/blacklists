#!/usr/bin/env python3
"""
Report what the whitelist is actually doing.

The whitelist is the last thing standing between an upstream mistake and a
user's broken machine, and it earned that description today: it caught
amazonaws.com, gravatar.com, vk.com and t.co when a parser change started
turning Adblock rule-cancellations into blocks.

Yet most of its entries match nothing on any given day, and it is tempting to
read that as dead weight. It is not. An entry only does its job on the day an
upstream list starts publishing that domain, so "matches nothing today" means
dormant, not useless. This report therefore classifies and explains, and never
removes anything:

  active   - a source is publishing this domain right now, and the whitelist is
             the only reason it is not in the release
  dormant  - no source publishes it today; it is standing by
  unknown  - the per-source downloads were unavailable, so nothing can be said

Run after generate.sh, while sources_raw/ is still populated:

    python3 scripts/whitelist_report.py [--annotate]

--annotate writes the evidence back into whitelist.txt as a trailing comment on
the active entries, so the file records why each one is there.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source_stats import supplier_normalize  # noqa: E402
from whitelist import parse_fqdn_line  # noqa: E402

WHITELIST = Path('whitelist.txt')
SOURCES_DIR = Path('sources_raw')
REGISTRY = Path('sources/registry.json')
OUTPUT = Path('stats/whitelist.json')


def log(message: str) -> None:
    print(message, flush=True)


def read_whitelist(path: Path) -> List[str]:
    """Read entries in file order, preserving duplicates for reporting."""
    with path.open(encoding='utf-8') as handle:
        return [d for d in (parse_fqdn_line(line) for line in handle) if d]


def find_suppliers(domains: Set[str], sources_dir: Path,
                   registry: Path) -> Dict[str, List[str]]:
    """Which sources are publishing each whitelisted domain right now."""
    if not sources_dir.is_dir():
        return {}

    names: Dict[str, str] = {}
    if registry.exists():
        entries = json.loads(registry.read_text(encoding='utf-8'))['sources']
        names = {entry['url']: entry['name'] for entry in entries}

    suppliers: Dict[str, List[str]] = defaultdict(list)
    for meta_path in sorted(sources_dir.glob('*.meta')):
        list_path = meta_path.with_suffix('.fqdn.list')
        if not list_path.exists():
            continue
        try:
            _, url, *_ = meta_path.read_text(encoding='utf-8').strip().split('\t')
        except ValueError:
            continue
        label = names.get(url, url)

        with list_path.open(encoding='utf-8', errors='ignore') as handle:
            for line in handle:
                domain = supplier_normalize(line)
                if domain in domains and label not in suppliers[domain]:
                    suppliers[domain].append(label)

    return dict(suppliers)


def annotate(path: Path, suppliers: Dict[str, List[str]], today: str) -> int:
    """Record on each active entry which source it was holding back, and when.

    Deliberately a dated snapshot rather than a live claim, and deliberately not
    run by the pipeline. Regenerating these every night would rewrite hundreds of
    lines a day and turn the file's history into noise; worse, an annotation
    that silently updates stops being evidence of why an entry was added.

    Only active entries are annotated. Inventing a reason for a dormant entry
    would put a guess in the file, and a guess here is worse than a blank.

    Existing comments are left alone: a reason someone wrote by hand outranks
    anything this script can infer.
    """
    lines = path.read_text(encoding='utf-8').splitlines()
    out: List[str] = []
    annotated = 0

    for line in lines:
        domain = parse_fqdn_line(line)
        has_comment = '#' in line
        who = suppliers.get(domain)

        if domain and who and not has_comment:
            reason = ', '.join(who[:3])
            if len(who) > 3:
                reason += f' +{len(who) - 3} more'
            out.append(f'{domain}  # {today}: blocked by {reason}')
            annotated += 1
        else:
            out.append(line)

    path.write_text('\n'.join(out) + '\n', encoding='utf-8')
    return annotated


def main() -> int:
    parser = argparse.ArgumentParser(description='Report whitelist effectiveness')
    parser.add_argument('--whitelist', default=str(WHITELIST))
    parser.add_argument('--sources-dir', default=str(SOURCES_DIR))
    parser.add_argument('--annotate', action='store_true',
                        help='Write the evidence back into whitelist.txt')
    args = parser.parse_args()

    path = Path(args.whitelist)
    if not path.is_file():
        print(f'FAIL: {path} not found', file=sys.stderr)
        return 1

    entries = read_whitelist(path)
    unique = set(entries)
    log(f'✓ Whitelist entries: {len(entries):,} ({len(unique):,} unique)')

    duplicates = sorted({d for d in entries if entries.count(d) > 1}) if \
        len(entries) != len(unique) else []

    sources_dir = Path(args.sources_dir)
    suppliers = find_suppliers(unique, sources_dir, REGISTRY)

    if not sources_dir.is_dir():
        log(f'Per-source downloads not found at {sources_dir}; run generate.sh '
            f'first to classify entries.')
        state = 'unknown'
    else:
        state = 'measured'

    active = sorted(suppliers)
    dormant = sorted(unique - set(active))

    payload = {
        'state': state,
        'entries': len(entries),
        'unique': len(unique),
        'active': len(active),
        'dormant': len(dormant),
        'duplicates': duplicates,
        'active_entries': [
            {'domain': domain, 'held_back_from': suppliers[domain]}
            for domain in active
        ],
    }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
                      encoding='utf-8')
    log(f'✓ Wrote {OUTPUT}')

    if state == 'measured':
        log('')
        log(f'  active  : {len(active):>5,}  a source is publishing these today')
        log(f'  dormant : {len(dormant):>5,}  standing by, nothing to hold back')
        if duplicates:
            log(f'  duplicates: {len(duplicates)} entry/entries listed more than once')

        log('')
        log('  Most contested entries (held back from the most sources):')
        for domain in sorted(active, key=lambda d: -len(suppliers[d]))[:10]:
            who = suppliers[domain]
            log(f'    {domain:32s} {len(who):>2} source(s): {", ".join(who[:3])}')

    if args.annotate:
        count = annotate(path, suppliers, date.today().isoformat())
        log('')
        log(f'✓ Annotated {count} active entries in {path}')

    # Reporting only. Nothing here is grounds for failing a build: a dormant
    # entry is doing exactly what it was added to do.
    return 0


if __name__ == '__main__':
    sys.exit(main())
