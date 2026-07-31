#!/usr/bin/env python3
"""
Measure what the published blacklist blocks among the domains people use.

A blocklist is easy to judge by size and hard to judge by correctness. This
script supplies the missing half: it ranks every blocked domain by real-world
popularity, names the source that introduced it, and refuses to let a release
ship if it blocks something that must never be blocked.

Three separate mechanisms, because one gate cannot serve all three purposes:

  1. sources/protected.txt - a small curated set of domains whose blocking
     breaks the machine rather than the page: DNS resolvers, OS update and
     certificate-validation endpoints, CDN apexes. Any hit fails the release.

  2. Popularity report - the most popular blocked domains with their Tranco
     rank and the source responsible. Published, not gated: 1,900 domains in
     the global top 10,000 are blocked entirely on purpose (doubleclick.net,
     google-analytics.com, criteo.com), so a naive "do not block popular
     domains" rule would fail on the project's whole reason to exist.

  3. sources/acknowledged.txt - the top-1000 blocks already reviewed. A domain
     entering the top 1000 that nobody has reviewed fails the release. This
     catches an upstream list changing under us, which is the failure mode
     nobody notices, without passing judgement on decisions already made.

Tranco is downloaded during the run and never redistributed, so it places no
licensing obligation on this repository.

Run: python3 scripts/check_quality.py --blacklist all.fqdn.blacklist
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_stats import supplier_normalize  # noqa: E402

TRANCO_URL = 'https://tranco-list.eu/top-1m.csv.zip'

PROTECTED = Path('sources/protected.txt')
ACKNOWLEDGED = Path('sources/acknowledged.txt')
REGISTRY = Path('sources/registry.json')
OUTPUT = Path('stats/quality.json')

# A domain entering this band without review fails the release.
REVIEW_RANK = 1000

# How many ranked entries to publish. The tail is long and uninformative; the
# head is what a user would notice.
REPORT_LIMIT = 250


def log(message: str) -> None:
    print(message, flush=True)


def read_domain_list(path: Path) -> Dict[str, Optional[str]]:
    """Read a curated list of ``domain  # reason`` lines.

    The reason is kept: a bare list of domains loses why each one is there,
    and an entry nobody can justify is an entry nobody dares remove.
    """
    entries: Dict[str, Optional[str]] = {}
    if not path.exists():
        return entries

    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            domain, _, reason = line.partition('#')
            domain = domain.strip().lower()
            if domain:
                entries[domain] = reason.strip() or None
    return entries


def load_blacklist(path: Path) -> Set[str]:
    domains = set()
    with path.open(encoding='utf-8', errors='ignore') as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith('#'):
                domains.add(line.lower())
    return domains


def load_tranco(cache: Optional[Path]) -> Dict[str, int]:
    """Fetch the Tranco top-1M ranking as {domain: rank}."""
    if cache and cache.exists():
        log(f'Using cached ranking from {cache}')
        payload = cache.read_bytes()
    else:
        log(f'Downloading ranking from {TRANCO_URL}...')
        request = urllib.request.Request(
            TRANCO_URL, headers={'User-Agent': 'fabriziosalmi-blacklists/1.0'}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
        if cache:
            cache.write_bytes(payload)

    ranks: Dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            for line in handle:
                rank, _, domain = line.decode().strip().partition(',')
                if domain:
                    ranks[domain.lower()] = int(rank)

    log(f'✓ Ranking loaded: {len(ranks):,} domains')
    return ranks


def attribute(domains: Set[str], sources_dir: Path, registry: Path) -> Dict[str, List[str]]:
    """Map each domain to the source lists that supplied it.

    Answers the question a maintainer actually has when a surprising domain
    shows up: who put it there. Silently returns nothing when the per-source
    downloads are unavailable, since the report is still useful without it.
    """
    if not sources_dir.is_dir():
        log('Per-source downloads not available, report will omit attribution')
        return {}

    names: Dict[str, str] = {}
    if registry.exists():
        entries = json.loads(registry.read_text(encoding='utf-8'))['sources']
        names = {entry['url']: entry['name'] for entry in entries}

    attribution: Dict[str, List[str]] = {}
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
                if domain in domains:
                    bucket = attribution.setdefault(domain, [])
                    if label not in bucket:
                        bucket.append(label)

    return attribution


def main() -> int:
    parser = argparse.ArgumentParser(description='Measure blacklist quality')
    parser.add_argument('--blacklist', default='all.fqdn.blacklist')
    parser.add_argument('--sources-dir', default='sources_raw')
    parser.add_argument('--cache', default=None,
                        help='Cache the downloaded ranking at this path')
    parser.add_argument('--write-acknowledged', action='store_true',
                        help='Rewrite acknowledged.txt from the current state '
                             'instead of failing. Establishes the baseline; not '
                             'for routine use.')
    args = parser.parse_args()

    blacklist_path = Path(args.blacklist)
    if not blacklist_path.is_file():
        print(f'FAIL: {blacklist_path} not found', file=sys.stderr)
        return 1

    log('=' * 60)
    log('Blacklist quality check')
    log('=' * 60)

    blacklist = load_blacklist(blacklist_path)
    log(f'✓ Published domains: {len(blacklist):,}')

    protected = read_domain_list(PROTECTED)
    acknowledged = read_domain_list(ACKNOWLEDGED)
    log(f'✓ Protected: {len(protected)}   acknowledged: {len(acknowledged)}')

    # --- 1. protected domains ------------------------------------------------
    # Deliberately first, and deliberately independent of the network: this is
    # the safety-critical check and it must run even when the ranking cannot be
    # fetched.
    violations = sorted(domain for domain in protected if domain in blacklist)

    # The popularity checks need a ranking. If it cannot be fetched, they are
    # skipped loudly rather than failing the release: an unreachable third-party
    # download says nothing about the quality of the list, and refusing to ship a
    # correct blacklist because tranco-list.eu is having a bad afternoon helps
    # nobody. The protected check above still stands.
    ranking_available = True
    try:
        ranks = load_tranco(Path(args.cache) if args.cache else None)
    except Exception as exc:  # network, DNS, zip corruption, HTTP error
        log(f'Warning: could not fetch the ranking ({exc}).')
        log('Popularity checks skipped; the protected-domain check still applies.')
        ranks = {}
        ranking_available = False

    # --- 2. popularity report ------------------------------------------------
    blocked_ranked = sorted(
        (rank, domain) for domain, rank in ranks.items() if domain in blacklist
    )
    bands = {
        f'top_{cut}': sum(1 for rank, _ in blocked_ranked if rank <= cut)
        for cut in (1000, 10000, 100000, 1000000)
    }

    top_entries = blocked_ranked[:REPORT_LIMIT]
    attribution = attribute({d for _, d in top_entries}, Path(args.sources_dir), REGISTRY)

    # --- 3. unreviewed entries in the review band ----------------------------
    in_band = [(rank, domain) for rank, domain in blocked_ranked if rank <= REVIEW_RANK]
    unacknowledged = [(r, d) for r, d in in_band if d not in acknowledged]

    if args.write_acknowledged:
        lines = [
            '# Domains in the global top 1000 that this list blocks.',
            '#',
            '# Presence here means the block has been looked at, not that it is',
            '# endorsed. A domain entering the top 1000 that is not listed here',
            '# fails the release, so that an upstream list changing under us is',
            '# noticed rather than shipped.',
            '#',
            '# Format: domain  # rank - source that supplied it',
            '',
        ]
        band_attribution = attribute({d for _, d in in_band}, Path(args.sources_dir), REGISTRY)
        for rank, domain in in_band:
            who = ', '.join(band_attribution.get(domain, [])) or 'source unrecorded'
            lines.append(f'{domain}  # rank {rank} - {who}')
        ACKNOWLEDGED.parent.mkdir(exist_ok=True)
        ACKNOWLEDGED.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        log(f'✓ Wrote baseline: {ACKNOWLEDGED} ({len(in_band)} entries)')
        unacknowledged = []

    # --- report --------------------------------------------------------------
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'ranking_source': 'Tranco top 1M (tranco-list.eu), fetched at build time',
        'ranking_available': ranking_available,
        'published_domains': len(blacklist),
        'protected': {
            'checked': len(protected),
            'violations': [
                {'domain': d, 'reason': protected[d]} for d in violations
            ],
        },
        'popularity': {
            'blocked_in_band': bands,
            'review_rank': REVIEW_RANK,
            'unacknowledged': [
                {'domain': d, 'rank': r, 'sources': attribution.get(d, [])}
                for r, d in unacknowledged
            ],
            'most_popular_blocked': [
                {'domain': d, 'rank': r, 'sources': attribution.get(d, [])}
                for r, d in top_entries
            ],
        },
    }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    log(f'✓ Wrote {OUTPUT}')

    log('')
    for band, count in bands.items():
        log(f'  blocked in {band.replace("_", " "):>16}: {count:>7,}')

    if violations:
        log('')
        log(f'FAIL: {len(violations)} protected domain(s) are blocked:')
        for domain in violations:
            reason = protected[domain] or 'no reason recorded'
            log(f'  - {domain}  ({reason})')
            for source in attribution.get(domain, []):
                log(f'      supplied by: {source}')
        return 1

    if not ranking_available:
        log('')
        log('✓ No protected domain blocked. Popularity checks did not run.')
        return 0

    if unacknowledged:
        log('')
        log(f'FAIL: {len(unacknowledged)} domain(s) newly blocked in the top '
            f'{REVIEW_RANK} and not yet reviewed:')
        for rank, domain in unacknowledged:
            who = ', '.join(attribution.get(domain, [])) or 'source unrecorded'
            log(f'  - #{rank} {domain}  <- {who}')
        log('')
        log(f'Review each one, then either whitelist it or add it to {ACKNOWLEDGED}.')
        return 1

    log('')
    log('✓ No protected domain blocked, no unreviewed entry in the top '
        f'{REVIEW_RANK}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
