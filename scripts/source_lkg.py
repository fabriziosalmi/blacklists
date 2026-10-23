#!/usr/bin/env python3
"""
Keep a last-known-good copy of every source, and use it when a source fails.

Two subcommands, run at two different points of the release:

    python3 scripts/source_lkg.py apply   # in generate.sh, after the downloads
    python3 scripts/source_lkg.py save    # in release.yml, after a good build

``apply`` looks at each source as downloaded into sources_raw/ and, when it is
missing or has collapsed, puts the last-known-good copy in its place:

  * missing: the fetch did not return a 2xx, or the archive held no domains
    file. From 2026-08-10 to 2026-08-13 five hagezi files returned 404 at once
    and the list lost 49% overnight; on 2026-10-22 three UT1 archives returned
    404 and the release was refused for -11.7%. Both were the upstream having a
    bad few days, not the domains ceasing to be dangerous.

  * collapsed: the fetch succeeded but the source lost more than
    MAX_SHRINK_FRACTION of its entries since the copy kept yesterday. Measured
    on 93 days of release logs (3,353 day-over-day pairs, every source with at
    least 1,000 entries), no source ever lost more than 25% in a day: the worst
    was hagezi TIF on 2026-10-08, -24.2%. 30% therefore fires only on what has
    never happened in normal operation, such as a truncated body or a 200 that
    carries an error page. (Measured on the pipeline-parsable count that
    source_stats.py logs; the count used here is a cheaper per-line proxy for
    it, compared only with itself from one day to the next.)

A copy is used for at most MAX_AGE_DAYS. A source that is gone for good must
eventually be seen to be gone, by the size gate and by a maintainer, rather
than be impersonated by an ever older snapshot.

``save`` refreshes the copies from today's downloads. A source that is on its
fallback keeps its old copy, so its age keeps counting; a source no longer in
blacklists.fqdn.urls loses its copy.

Copies are keyed by a hash of the URL, never by the download index: the index
is a position in blacklists.fqdn.urls and shifts whenever a line is added above.

Storage is the directory passed as --lkg-dir. In the release workflow it is
restored from and saved to the Actions cache; locally it is simply absent, and
``apply`` then changes nothing.

Every decision is written to sources_raw/NNN.fallback (read by source_stats.py)
and summarised in sources_raw/lkg.json. Both live and die with the downloads:
source_stats.py carries the decisions into stats/sources.json, which is what
gets published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# A source that lost more than this fraction of its entries since the kept copy
# is treated as collapsed. See the module docstring for how it was measured.
MAX_SHRINK_FRACTION = 0.30

# Below this many entries lost, a percentage says nothing: a list of 40 losing
# 15 is ordinary maintenance, not a broken fetch.
MIN_SHRINK_ENTRIES = 1_000

# Longest a kept copy may stand in for its source.
MAX_AGE_DAYS = 7

MANIFEST = 'manifest.json'
REPORT_NAME = 'lkg.json'


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]


def count_entries(path: Path) -> int:
    """Lines that could carry a domain, in any of the formats sources use.

    Deliberately cheap and format-agnostic: hosts files, plain lists and
    Adblock rules all count one per line, while comments, section headers,
    blank lines and markup do not. It only has to be comparable with itself
    from one day to the next.
    """
    count = 0
    with path.open(encoding='utf-8', errors='ignore') as handle:
        for line in handle:
            line = line.strip()
            if not line or line[0] in '#![' or '<' in line:
                continue
            count += 1
    return count


def read_meta(path: Path) -> Optional[Dict]:
    try:
        index, url, status, *_ = path.read_text(encoding='utf-8').strip().split('\t')
    except ValueError:
        return None
    return {'index': int(index), 'url': url, 'status': status}


def load_manifest(lkg_dir: Path) -> Dict[str, Dict]:
    path = lkg_dir / MANIFEST
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        # A corrupt manifest must not take the release down with it; it only
        # means there is no fallback tonight.
        print(f'warning: unreadable {path}, ignoring the kept copies')
        return {}


def age_days(saved_at: str, now: datetime) -> float:
    saved = datetime.fromisoformat(saved_at)
    return (now - saved).total_seconds() / 86400


def decide(fresh_entries: Optional[int], kept: Optional[Dict], kept_age: Optional[float],
           max_age: float = MAX_AGE_DAYS) -> Optional[str]:
    """Why the kept copy should replace today's download, or None to keep it.

    ``fresh_entries`` is None when the download failed.
    """
    usable = kept is not None and kept_age is not None and kept_age <= max_age
    if not usable:
        return None
    if fresh_entries is None:
        return 'download failed'
    lost = kept['entries'] - fresh_entries
    if lost >= MIN_SHRINK_ENTRIES and lost > kept['entries'] * MAX_SHRINK_FRACTION:
        return (f'collapsed from {kept["entries"]:,} to {fresh_entries:,} entries '
                f'(-{lost / kept["entries"]:.0%})')
    return None


def apply(sources_dir: Path, lkg_dir: Path, now: datetime) -> int:
    manifest = load_manifest(lkg_dir)
    decisions: List[Dict] = []

    for meta_path in sorted(sources_dir.glob('*.meta')):
        meta = read_meta(meta_path)
        if meta is None:
            continue
        target = meta_path.with_suffix('.fqdn.list')
        key = url_key(meta['url'])
        kept = manifest.get(key)
        kept_file = lkg_dir / f'{key}.list'
        if kept is not None and not kept_file.is_file():
            kept = None
        kept_age = age_days(kept['saved_at'], now) if kept else None

        fresh_entries = count_entries(target) if target.is_file() else None
        reason = decide(fresh_entries, kept, kept_age)

        if reason is None:
            if fresh_entries is None:
                why = ('no kept copy' if kept is None
                       else f'kept copy is {kept_age:.1f} days old, beyond {MAX_AGE_DAYS}')
                decisions.append({'index': meta['index'], 'url': meta['url'],
                                  'fallback': False, 'excluded': True, 'detail': why})
            continue

        shutil.copyfile(kept_file, target)
        record = {
            'index': meta['index'],
            'url': meta['url'],
            'fallback': True,
            'reason': reason,
            'http_status': meta['status'],
            'fresh_entries': fresh_entries,
            'kept_entries': kept['entries'],
            'kept_saved_at': kept['saved_at'],
            'kept_age_days': round(kept_age, 2),
        }
        meta_path.with_suffix('.fallback').write_text(
            json.dumps(record, indent=2) + '\n', encoding='utf-8')
        decisions.append(record)

    on_fallback = [d for d in decisions if d['fallback']]
    excluded = [d for d in decisions if d.get('excluded')]

    (sources_dir / REPORT_NAME).write_text(json.dumps({
        'generated_at': now.isoformat(),
        'kept_copies': len(manifest),
        'max_age_days': MAX_AGE_DAYS,
        'max_shrink_fraction': MAX_SHRINK_FRACTION,
        'on_fallback': on_fallback,
        'excluded': excluded,
    }, indent=2) + '\n', encoding='utf-8')

    if not manifest:
        print('Last-known-good: no kept copies available, downloads used as they are.')
    for d in on_fallback:
        print(f'! Source {d["index"]} {d["reason"]}: using the copy kept '
              f'{d["kept_age_days"]:.1f} days ago ({d["kept_entries"]:,} entries): {d["url"]}')
    for d in excluded:
        print(f'✗ Source {d["index"]} failed and has no usable copy ({d["detail"]}): {d["url"]}')
    if manifest and not on_fallback and not excluded:
        print(f'✓ Last-known-good: all sources fresh ({len(manifest)} copies kept)')
    return 0


def save(sources_dir: Path, lkg_dir: Path, now: datetime) -> int:
    lkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(lkg_dir)
    current = {}
    refreshed = kept_old = 0

    for meta_path in sorted(sources_dir.glob('*.meta')):
        meta = read_meta(meta_path)
        if meta is None:
            continue
        key = url_key(meta['url'])
        current[key] = meta['url']
        target = meta_path.with_suffix('.fqdn.list')

        # A source on its fallback is holding yesterday's copy; refreshing the
        # copy from it would reset its age and let it stand in forever.
        if meta_path.with_suffix('.fallback').is_file() or not target.is_file():
            kept_old += key in manifest
            continue

        shutil.copyfile(target, lkg_dir / f'{key}.list')
        manifest[key] = {
            'url': meta['url'],
            'saved_at': now.isoformat(),
            'entries': count_entries(target),
        }
        refreshed += 1

    dropped = [key for key in manifest if key not in current]
    for key in dropped:
        manifest.pop(key)
        (lkg_dir / f'{key}.list').unlink(missing_ok=True)

    (lkg_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                                    encoding='utf-8')
    print(f'✓ Last-known-good saved: {refreshed} refreshed, {kept_old} kept from before, '
          f'{len(dropped)} dropped (no longer configured)')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Last-known-good copies of the sources')
    parser.add_argument('command', choices=('apply', 'save'))
    parser.add_argument('--sources-dir', default='sources_raw', type=Path)
    parser.add_argument('--lkg-dir', default='sources_lkg', type=Path)
    args = parser.parse_args()

    if not args.sources_dir.is_dir():
        print(f'FAIL: {args.sources_dir} not found', file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    if args.command == 'apply':
        return apply(args.sources_dir, args.lkg_dir, now)
    return save(args.sources_dir, args.lkg_dir, now)


if __name__ == '__main__':
    sys.exit(main())
