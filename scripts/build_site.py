#!/usr/bin/env python3
"""
Build the GitHub Pages site into a self-contained directory.

The site is built from three inputs:

  1. ``docs/``            static assets (HTML/CSS/JS/fonts), copied verbatim
  2. ``stats/``           the committed statistics time series
  3. ``blacklist.txt``    the published release asset, used to build the lookup index

Everything the page renders is produced here, so the browser never has to call
the GitHub API and never has to fall back to hardcoded numbers. If an input is
missing the build fails loudly rather than publishing a plausible-looking site
backed by stale or invented data.

The domain lookup index is a static sharded set: each domain is hashed with
SHA-256 and filed into a shard named after the first ``PREFIX_LEN`` hex
characters of the digest. A client hashes the domain it wants to check, fetches
the single matching shard (~25 KB) and tests for membership. Exact answers, no
false positives, no server.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

# Number of leading hex characters of the SHA-256 digest used as the shard name.
# 3 characters -> 4096 shards -> roughly 1,200 domains (~25 KB) per shard.
PREFIX_LEN = 3
SHARD_COUNT = 16 ** PREFIX_LEN

# Flush buffered shard lines to disk every N domains to bound memory use.
FLUSH_EVERY = 500_000

# A build producing fewer domains than this almost certainly means a truncated
# or failed download. Refuse to publish it.
MIN_PLAUSIBLE_DOMAINS = 1_000_000


def log(message: str) -> None:
    print(message, flush=True)


def iter_domains(blacklist: Path) -> Iterator[str]:
    """Yield normalized domains from the published blacklist artifact.

    The artifact carries a ``#``-prefixed attribution header, so comments and
    blank lines are skipped here exactly as the RPZ/Unbound converters do.
    """
    with blacklist.open('r', encoding='utf-8', errors='ignore') as handle:
        for line in handle:
            domain = line.strip()
            if not domain or domain.startswith('#'):
                continue
            yield domain.lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build_shards(blacklist: Path, out_dir: Path) -> int:
    """Write the sharded lookup index and return the number of domains indexed."""
    shard_dir = out_dir / 'data' / 'shards'
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    shard_dir.mkdir(parents=True)

    buffers: Dict[str, List[str]] = defaultdict(list)
    total = 0

    def flush() -> None:
        for shard, lines in buffers.items():
            with (shard_dir / f'{shard}.txt').open('a', encoding='utf-8') as handle:
                handle.write('\n'.join(lines))
                handle.write('\n')
        buffers.clear()

    for domain in iter_domains(blacklist):
        digest = hashlib.sha256(domain.encode('utf-8')).hexdigest()
        buffers[digest[:PREFIX_LEN]].append(domain)
        total += 1
        if total % FLUSH_EVERY == 0:
            flush()
            log(f'  indexed {total:,} domains...')

    flush()

    if total < MIN_PLAUSIBLE_DOMAINS:
        raise SystemExit(
            f'Refusing to publish: only {total:,} domains indexed, expected at '
            f'least {MIN_PLAUSIBLE_DOMAINS:,}. The blacklist download is likely '
            f'truncated or failed.'
        )

    # Shards that received no domains still need to exist, otherwise a lookup
    # landing on an empty shard gets a 404 and cannot tell "not listed" apart
    # from "index broken".
    created = 0
    for value in range(SHARD_COUNT):
        shard_file = shard_dir / f'{value:0{PREFIX_LEN}x}.txt'
        if not shard_file.exists():
            shard_file.touch()
            created += 1
    if created:
        log(f'  created {created} empty shards')

    log(f'✓ Indexed {total:,} domains into {SHARD_COUNT} shards')
    return total


def load_history(history_csv: Path) -> List[Dict]:
    """Load the committed daily time series."""
    if not history_csv.exists():
        log(f'Warning: {history_csv} not found, history will be empty')
        return []

    history: List[Dict] = []
    with history_csv.open('r', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            try:
                history.append({
                    'date': row['date'],
                    'total_domains': int(row['total_domains']),
                    'whitelisted': int(row.get('whitelisted') or 0),
                    'sources': int(row.get('sources') or 0),
                })
            except (KeyError, ValueError):
                continue

    history.sort(key=lambda entry: entry['date'])
    log(f'✓ Loaded {len(history)} days of history')
    return history


def load_sources(repo: Path, stats_dir: Path) -> Dict:
    """Merge the curated source registry with the latest measured metrics.

    ``sources/registry.json`` is the curated truth about each upstream list
    (project, maintainer, licence and the evidence for it). ``stats/sources.json``
    is written by the release pipeline and carries what actually happened on the
    last run (HTTP status, domains contributed, unique contribution).

    The registry is required: publishing aggregated lists without their
    attribution and licences is the one thing this site must not do. Metrics are
    optional - until the pipeline has run once, sources are listed with no
    numbers rather than with invented ones.
    """
    registry_file = repo / 'sources' / 'registry.json'
    if not registry_file.exists():
        raise SystemExit(
            f'Refusing to publish: {registry_file} not found. The site must not '
            f'redistribute third-party lists without their attribution and licences.'
        )

    registry = json.loads(registry_file.read_text(encoding='utf-8'))
    entries = registry.get('sources', [])

    measured: Dict[str, Dict] = {}
    measured_at: Optional[str] = None
    categories: List[Dict] = []
    metrics_file = stats_dir / 'sources.json'
    if metrics_file.exists():
        try:
            payload = json.loads(metrics_file.read_text(encoding='utf-8'))
            measured_at = payload.get('generated_at')
            categories = payload.get('categories', [])
            measured = {
                item['url']: item
                for item in payload.get('sources', [])
                if item.get('url')
            }
        except (json.JSONDecodeError, KeyError) as exc:
            log(f'Warning: could not parse {metrics_file}: {exc}')

    merged = []
    for entry in entries:
        item = dict(entry)
        item['metrics'] = measured.get(entry['url'])
        merged.append(item)

    matched = sum(1 for item in merged if item['metrics'])
    log(f'✓ Registry: {len(merged)} sources, {matched} with measured metrics')

    return {
        'measured': bool(measured),
        'measured_at': measured_at,
        'licenses_verified_at': registry.get('licenses_verified_at'),
        'categories': categories,
        'sources': merged,
    }


def write_badges(badge_dir: Path, stats: Dict) -> None:
    """Write shields.io endpoint payloads so README badges track the real data."""
    badge_dir.mkdir(parents=True, exist_ok=True)

    def compact(value: int) -> str:
        if value >= 1_000_000:
            return f'{value / 1_000_000:.2f}M'
        if value >= 1_000:
            return f'{value / 1_000:.1f}k'
        return str(value)

    badges = {
        'domains': {
            'label': 'blocked domains',
            'message': compact(stats['total_domains']),
            'color': 'cc0000',
        },
        'sources': {
            'label': 'sources',
            'message': str(stats['blacklist_sources']),
            'color': '000000',
        },
        'whitelisted': {
            'label': 'whitelisted',
            'message': f"{stats['whitelisted_domains']:,}",
            'color': '00cc00',
        },
        'updated': {
            'label': 'updated',
            'message': (stats.get('generated_at') or '')[:10] or 'unknown',
            'color': '2563eb',
        },
    }

    for name, payload in badges.items():
        payload['schemaVersion'] = 1
        (badge_dir / f'{name}.json').write_text(
            json.dumps(payload, indent=2), encoding='utf-8'
        )

    log(f'✓ Wrote {len(badges)} badge endpoints')


def copy_static(docs_dir: Path, out_dir: Path) -> None:
    if not docs_dir.is_dir():
        raise SystemExit(f'Static source directory not found: {docs_dir}')

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(docs_dir, out_dir)

    # Markdown docs live alongside the site source but are rendered on GitHub,
    # not served as pages. Leaving them out keeps the artifact honest about what
    # the site actually publishes.
    for markdown in out_dir.glob('*.md'):
        markdown.unlink()

    # Jekyll would otherwise ignore any path starting with an underscore.
    (out_dir / '.nojekyll').touch()

    log(f'✓ Copied static assets from {docs_dir}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the Pages site')
    parser.add_argument('--repo-path', default='.', help='Repository root')
    parser.add_argument('--blacklist', required=True,
                        help='Path to the downloaded blacklist.txt release asset')
    parser.add_argument('--out', default='_site', help='Output directory')
    parser.add_argument('--release-tag', default=os.environ.get('RELEASE_TAG', ''))
    parser.add_argument('--release-published-at',
                        default=os.environ.get('RELEASE_PUBLISHED_AT', ''))
    parser.add_argument('--run-url', default=os.environ.get('RUN_URL', ''))
    args = parser.parse_args()

    repo = Path(args.repo_path).resolve()
    out_dir = Path(args.out).resolve()
    blacklist = Path(args.blacklist).resolve()
    stats_dir = repo / 'stats'

    if not blacklist.is_file():
        raise SystemExit(f'Blacklist artifact not found: {blacklist}')

    log('=' * 60)
    log('Building site')
    log('=' * 60)

    copy_static(repo / 'docs', out_dir)

    data_dir = out_dir / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    log('Hashing release artifact...')
    blacklist_sha256 = file_sha256(blacklist)
    blacklist_bytes = blacklist.stat().st_size

    log('Building lookup index...')
    total_domains = build_shards(blacklist, out_dir)

    history = load_history(stats_dir / 'history.csv')

    daily_stats: Dict = {}
    daily_file = stats_dir / 'daily_stats.json'
    if daily_file.exists():
        daily_stats = json.loads(daily_file.read_text(encoding='utf-8'))

    # The domain count is taken from the artifact we actually indexed, not from
    # the stats file, so the number on the page always matches the file users
    # download and the index they are querying.
    whitelisted = daily_stats.get('whitelisted_domains')
    if whitelisted is None:
        whitelisted = sum(1 for _ in (repo / 'whitelist.txt').open(encoding='utf-8')) \
            if (repo / 'whitelist.txt').exists() else 0

    # Counted from the registry rather than from daily_stats.json: the registry
    # is validated against the URL list the pipeline actually fetches, so it
    # cannot disagree with the source table rendered on the same page. The stats
    # file is written by a separate schedule and lags whenever sources change.
    sources_data = load_sources(repo, stats_dir)
    sources_count = len(sources_data['sources'])

    stats = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_domains': total_domains,
        'whitelisted_domains': whitelisted,
        'blacklist_sources': sources_count,
        'changes': daily_stats.get('changes', {}),
        'stats_generated_at': daily_stats.get('generated_at'),
        'release': {
            'tag': args.release_tag or None,
            'published_at': args.release_published_at or None,
            'blacklist_sha256': blacklist_sha256,
            'blacklist_bytes': blacklist_bytes,
        },
        'build': {
            'run_url': args.run_url or None,
        },
        'index': {
            'scheme': 'sha256',
            'prefix_length': PREFIX_LEN,
            'shard_count': SHARD_COUNT,
        },
        # What a reader is actually installing. Carried in stats.json as well as
        # sources.json so the headline figure and its breakdown always come from
        # the same document.
        'categories': sources_data.get('categories', []),
    }

    # How much of the whitelist is doing work right now. Published so the
    # "whitelisted domains" figure is not mistaken for a count of active
    # protections when most entries are dormant by design. Merged before
    # stats.json is written, not after.
    whitelist_file = stats_dir / 'whitelist.json'
    if whitelist_file.exists():
        try:
            payload = json.loads(whitelist_file.read_text(encoding='utf-8'))
            stats['whitelist'] = {
                'entries': payload.get('unique'),
                'active': payload.get('active'),
                'dormant': payload.get('dormant'),
            }
            # This count comes from the same run that produced the artifact,
            # where daily_stats.json is written on its own schedule and lags by a
            # day. The headline figure and its breakdown must not disagree.
            if payload.get('unique'):
                stats['whitelisted_domains'] = payload['unique']
        except json.JSONDecodeError as exc:
            log(f'Warning: could not parse {whitelist_file}: {exc}')

    (data_dir / 'stats.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    (data_dir / 'history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    (data_dir / 'sources.json').write_text(
        json.dumps(sources_data, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    # The quality report answers the question size cannot: what does this list
    # block among the domains people actually use. Absent until the pipeline has
    # produced one, in which case the page says so instead of implying a clean
    # result that was never measured.
    quality_file = stats_dir / 'quality.json'
    if quality_file.exists():
        (data_dir / 'quality.json').write_text(
            quality_file.read_text(encoding='utf-8'), encoding='utf-8'
        )
        log('✓ Published quality report')
    else:
        log('Warning: no stats/quality.json, the site will report it as unmeasured')

    # Served as the index manifest so a client can verify the shard scheme it is
    # querying instead of assuming it.
    (data_dir / 'index.json').write_text(json.dumps({
        'scheme': 'sha256',
        'prefix_length': PREFIX_LEN,
        'shard_count': SHARD_COUNT,
        'total_domains': total_domains,
        'generated_at': stats['generated_at'],
        'blacklist_sha256': blacklist_sha256,
    }, indent=2), encoding='utf-8')

    write_badges(data_dir / 'badges', stats)

    log('=' * 60)
    log(f'✓ Site built at {out_dir}')
    log(f'  domains indexed : {total_domains:,}')
    log(f'  history points  : {len(history)}')
    log(f'  artifact sha256 : {blacklist_sha256[:16]}...')
    log('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
