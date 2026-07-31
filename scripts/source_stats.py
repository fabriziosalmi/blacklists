#!/usr/bin/env python3
"""
Attribute the aggregated blacklist back to the sources that supplied it.

Run this after generate.sh, while sources_raw/ still holds one downloaded file
per source:

    python3 scripts/source_stats.py

It answers, for every configured source, the questions a user of an aggregated
list should be able to ask:

  * did today's fetch actually work, and what did the server return?
  * how many domains from this source survived into the published list?
  * how many of those came from this source ALONE - that is, what would be lost
    if it were dropped?

"Contribution" is measured against the published list rather than by re-running
validation, so the numbers describe the file people download rather than an
independent estimate of it. A domain is credited to a source when the source
supplied it and it survived sanitisation and whitelisting.

Output: stats/sources.json
"""

from __future__ import annotations

import json
import re
import sys
from array import array
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# sanitize.py lives at the repository root, which is not on sys.path when this
# script runs as `python3 scripts/source_stats.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sanitize import (  # noqa: E402  (import needs the path set above)
    get_sanitization_rules as _get_sanitization_rules,
    sanitize_line as _sanitize_line,
)

_SANITIZE_RULES = _get_sanitization_rules()

SOURCES_DIR = Path('sources_raw')
BLACKLIST = Path('all.fqdn.blacklist')
REGISTRY = Path('sources/registry.json')
OUTPUT = Path('stats/sources.json')

HTML_MARKERS = ('<!doctype', '<html', '<head', '<body')

IP_PATTERN = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')
# Mirrors FQDN_PATTERN in sanitize.py, applied per label.
LABEL_PATTERN = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')


def supplier_normalize(line: str) -> Optional[str]:
    """Extract the domain a source *intended* to list.

    Lenient on purpose: it understands hosts files, trailing comments and
    Adblock syntax. This is used for attribution - "which source supplied this
    published domain" - and is independent of whether the pipeline can currently
    read that syntax.
    """
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('!') or line.startswith('['):
        return None

    for prefix in ('http://', 'https://'):
        if line.startswith(prefix):
            line = line[len(prefix):]
            break

    # Adblock syntax: ||example.com^$modifier
    if line.startswith('||'):
        line = line[2:]
    line = line.split('^')[0].split('$')[0]

    # hosts syntax: the address comes first, the hostname second.
    parts = line.split()
    if not parts:
        return None
    if IP_PATTERN.match(parts[0]) or parts[0] in ('127.0.0.1', '0.0.0.0'):
        if len(parts) < 2:
            return None
        line = parts[1]
    else:
        line = parts[0]

    # Trailing inline comment, e.g. "example.com #tracker"
    line = line.split('#')[0].split('/')[0]
    line = line.rstrip('.').lower()

    if not line or '.' not in line or '*' in line:
        return None
    return line


def pipeline_normalize(line: str) -> Optional[str]:
    """Report what sanitize.py makes of one line.

    The strict counterpart of supplier_normalize. Comparing the two reveals
    sources whose syntax the pipeline cannot parse: entries a human would read
    as domains but that sanitize.py discards.

    It calls sanitize.py rather than reimplementing it. An earlier version kept
    a parallel copy of the rules and silently fell out of step the moment the
    Adblock parsing changed, which would have reported sources as readable when
    the pipeline had stopped reading them - the exact blindness this function
    exists to remove.

    The only check omitted is tldextract's public-suffix lookup, which rejects
    strictly more lines, so this is an upper bound on what the pipeline keeps.
    """
    result = _sanitize_line(line, _SANITIZE_RULES)
    if not result or '*' in result or '.' not in result:
        return None
    if not all(LABEL_PATTERN.match(label) for label in result.split('.')):
        return None
    return result


def detect_format(sample: List[str]) -> str:
    """Classify a source by what it actually served, not by what it claims."""
    joined = '\n'.join(sample[:40]).lower()

    if any(marker in joined for marker in HTML_MARKERS):
        return 'html'

    for line in sample:
        line = line.strip()
        if not line:
            continue
        if line.startswith('[Adblock') or line.startswith('[adblock'):
            return 'adblock'
        if line.startswith('{') or line.startswith('['):
            return 'json'
        if line.startswith('#') or line.startswith('!'):
            continue
        if line.startswith('||'):
            return 'adblock'
        if line.startswith('127.0.0.1') or line.startswith('0.0.0.0'):
            return 'hosts'
        if line.startswith('http://') or line.startswith('https://'):
            return 'url'
        return 'domains'

    return 'empty'


def read_meta(path: Path) -> Optional[Dict]:
    """Read one tab-separated download record written by generate.sh."""
    try:
        index, url, status, size, elapsed = path.read_text(encoding='utf-8').strip().split('\t')
    except (ValueError, OSError):
        return None

    return {
        'index': int(index),
        'url': url,
        'http_status': int(status) if status.isdigit() else 0,
        'bytes': int(size),
        'fetch_seconds': int(elapsed),
    }


def load_final_domains(path: Path) -> Dict[str, int]:
    """Map every published domain to a dense index."""
    final: Dict[str, int] = {}
    with path.open(encoding='utf-8', errors='ignore') as handle:
        for line in handle:
            domain = line.strip()
            if not domain or domain.startswith('#'):
                continue
            if domain not in final:
                final[domain] = len(final)
    return final


def summarise_categories(per_source, registry_entries: Dict[str, Dict],
                         published: int) -> List[Dict]:
    """Count published domains by the category of the sources that supplied them.

    Someone installing what reads as an ads-and-malware list also receives
    gambling, piracy and streaming blocks. That is a defensible editorial choice
    but not a silent one, so the split is measured and published.

    Two numbers per category, because they answer different questions:

    * ``domains``   - how many published domains at least one source in this
      category supplied. Categories overlap heavily, so these do not sum to the
      list total and are not meant to.
    * ``exclusive`` - how many arrive from this category and nowhere else, i.e.
      what would actually be lost by dropping it. This is the number that tells
      a reader whether a category is load-bearing or merely along for the ride.
    """
    names = sorted({
        category
        for entry in registry_entries.values()
        for category in entry.get('categories', [])
    })
    if not names:
        return []

    if len(names) > 32:  # one bit per category, held in a 32-bit word
        print(f'Warning: {len(names)} categories, only the first 32 are counted')
        names = names[:32]

    bit = {name: 1 << index for index, name in enumerate(names)}

    # One mask per published domain recording which categories reached it. The
    # length is derived from itemsize rather than assumed: 'I' is only
    # guaranteed to be at least two bytes, and sizing it by hand silently
    # allocates the wrong number of slots.
    masks = array('I', bytes(published * array('I').itemsize))

    for record, _, indices in per_source:
        entry = registry_entries.get(record['url'])
        if not entry:
            continue
        mask = 0
        for category in entry.get('categories', []):
            mask |= bit.get(category, 0)
        if not mask:
            continue
        for idx in indices:
            masks[idx] |= mask

    summary = []
    for name in names:
        flag = bit[name]
        total = exclusive = 0
        for mask in masks:
            if mask & flag:
                total += 1
                if mask == flag:
                    exclusive += 1
        summary.append({'category': name, 'domains': total, 'exclusive': exclusive})

    summary.sort(key=lambda item: -item['domains'])
    return summary


def main() -> int:
    if not BLACKLIST.exists():
        print(f'FAIL: {BLACKLIST} not found - run generate.sh first', file=sys.stderr)
        return 1
    if not SOURCES_DIR.is_dir():
        print(f'FAIL: {SOURCES_DIR}/ not found - run generate.sh first', file=sys.stderr)
        return 1

    registry_entries: Dict[str, Dict] = {}
    if REGISTRY.exists():
        registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
        registry_entries = {e['url']: e for e in registry.get('sources', [])}

    print('Loading published blacklist...')
    final = load_final_domains(BLACKLIST)
    print(f'  {len(final):,} published domains')

    metas = sorted(SOURCES_DIR.glob('*.meta'))
    if not metas:
        print(f'FAIL: no download records in {SOURCES_DIR}/', file=sys.stderr)
        return 1

    # Saturating per-domain contributor counter, used to find domains that only
    # one source supplied.
    contributors = bytearray(len(final))
    per_source: List[Tuple[Dict, Optional[Path], List[int]]] = []

    print('Pass 1: attributing domains...')
    for meta_path in metas:
        meta = read_meta(meta_path)
        if meta is None:
            print(f'  warning: unreadable record {meta_path}')
            continue

        list_path = meta_path.with_suffix('.fqdn.list')
        record = dict(meta)
        indices: List[int] = []

        if not list_path.exists():
            # Download failed; the record still describes what happened.
            record.update({
                'ok': False,
                'format': None,
                'raw_lines': 0,
                'candidates': 0,
                'domains': 0,
                'unique_domains': 0,
                'error': f'HTTP {meta["http_status"]}' if meta['http_status'] else 'fetch failed',
            })
            per_source.append((record, None, indices))
            continue

        raw_lines = 0
        candidates = 0
        pipeline_parsed = 0
        seen = set()
        sample: List[str] = []

        with list_path.open(encoding='utf-8', errors='ignore') as handle:
            for line in handle:
                raw_lines += 1
                if len(sample) < 40:
                    sample.append(line)

                if pipeline_normalize(line) is not None:
                    pipeline_parsed += 1

                domain = supplier_normalize(line)
                if domain is None:
                    continue
                candidates += 1

                idx = final.get(domain)
                if idx is not None and domain not in seen:
                    seen.add(domain)
                    indices.append(idx)
                    if contributors[idx] < 255:
                        contributors[idx] += 1

        # A source that offers domains the pipeline cannot parse is silently
        # doing nothing. That is worth stating outright rather than leaving it
        # to be inferred from a zero.
        unreadable = candidates > 0 and pipeline_parsed == 0

        record.update({
            'ok': True,
            'format': detect_format(sample),
            'raw_lines': raw_lines,
            'candidates': candidates,
            'pipeline_parsed': pipeline_parsed,
            'unreadable_by_pipeline': unreadable,
            'domains': len(indices),
            'error': None,
        })
        per_source.append((record, list_path, indices))

        flag = '  [UNREADABLE BY PIPELINE]' if unreadable else ''
        print(f'  [{record["index"]:>3}] {record["domains"]:>9,} attributed  '
              f'{pipeline_parsed:>9,} parsable  {record["url"][:58]}{flag}')

    print('Pass 2: computing unique contributions...')
    results = []
    for record, _, indices in per_source:
        record['unique_domains'] = sum(1 for idx in indices if contributors[idx] == 1)

        entry = registry_entries.get(record['url'])
        if entry:
            record['id'] = entry['id']
            record['name'] = entry['name']
            record['categories'] = entry.get('categories', [])
        results.append(record)

    results.sort(key=lambda r: r['index'])

    categories = summarise_categories(per_source, registry_entries, len(final))

    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'published_domains': len(final),
        'sources_configured': len(results),
        'sources_ok': sum(1 for r in results if r['ok']),
        'sources_failed': sum(1 for r in results if not r['ok']),
        'sources_unreadable': sum(1 for r in results if r.get('unreadable_by_pipeline')),
        'categories': categories,
        'sources': results,
    }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print()
    print(f'✓ Wrote {OUTPUT}')
    print(f'  sources ok      : {payload["sources_ok"]}/{payload["sources_configured"]}')
    if payload['sources_failed']:
        print(f'  sources failed  : {payload["sources_failed"]}')
        for record in results:
            if not record['ok']:
                print(f'    - {record["error"]}: {record["url"]}')

    unreadable = [r for r in results if r.get('unreadable_by_pipeline')]
    if unreadable:
        print(f'  unreadable      : {len(unreadable)} source(s) offer domains that '
              f'sanitize.py cannot parse, so they contribute nothing:')
        for record in unreadable:
            print(f'    - format={record["format"]:8s} {record["candidates"]:>8,} offered  {record["url"]}')

    empty = [r for r in results if r['ok'] and r['domains'] == 0
             and not r.get('unreadable_by_pipeline')]
    if empty:
        print(f'  contributed nothing: {len(empty)}')
        for record in empty:
            print(f'    - format={record["format"]}: {record["url"]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
