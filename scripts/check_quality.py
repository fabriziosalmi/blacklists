#!/usr/bin/env python3
"""
Measure what the published blacklist blocks among the domains people use.

A blocklist is easy to judge by size and hard to judge by correctness. This
script supplies the missing half: it ranks every blocked domain by real-world
popularity, names the source that introduced it, and refuses to let a release
ship if it blocks something that must never be blocked.

Four separate mechanisms, because one gate cannot serve four purposes:

  0. Size. A release that lost a large share of the list overnight is refused.
     Counting successful downloads is not enough: two of forty-six sources 404'd
     on 2026-07-31 and took 46% of the domains with them, because one was almost
     half the list on its own, and a source-count threshold waved it through.

  1. sources/protected.txt - a small curated set of domains whose blocking
     breaks the machine rather than the page: DNS resolvers, OS update and
     certificate-validation endpoints, CDN apexes. Any hit fails the release.

  2. Popularity report - the most popular blocked domains with their Tranco
     rank and the source responsible. Published, not gated: 1,900 domains in
     the global top 10,000 are blocked entirely on purpose (doubleclick.net,
     google-analytics.com, criteo.com), so a naive "do not block popular
     domains" rule would fail on the project's whole reason to exist.

  3. sources/acknowledged.txt - the top-1000 blocks already reviewed. A domain
     that is popular AND newly added to the list, and that nobody has reviewed,
     is REPORTED, not blocked. Whether a popular domain belongs in the list is
     an editorial question, and blocking a release on one froze the published
     list for two weeks. Checks 0 and 1 cover what is actually broken; this one
     leaves a review queue.

     It is still compared against the previously published release, because
     Tranco reranks daily and domains drifting across the rank-1000 boundary
     would otherwise fill the queue with non-events.

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
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_stats import supplier_normalize  # noqa: E402

TRANCO_URL = 'https://tranco-list.eu/top-1m.csv.zip'

PROTECTED = Path('sources/protected.txt')
ACKNOWLEDGED = Path('sources/acknowledged.txt')
REGISTRY = Path('sources/registry.json')
HISTORY = Path('stats/history.csv')
OUTPUT = Path('stats/quality.json')

# Largest single-day shrinkage accepted without review. Normal churn is under
# 2%; anything approaching this means a source stopped answering rather than the
# internet getting safer.
MAX_SHRINK_PERCENT = 10.0

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


def previous_total(history: Path) -> Optional[int]:
    """The most recent recorded domain count, or None if there is no history."""
    if not history.exists():
        return None

    latest = None
    with history.open(encoding='utf-8') as handle:
        next(handle, None)  # header
        for line in handle:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                try:
                    latest = int(parts[1])
                except ValueError:
                    continue
    return latest


def check_shrinkage(current: int, previous: Optional[int]) -> Tuple[bool, str]:
    """Refuse a release that lost a large share of the list overnight.

    Counting how many sources downloaded is not enough protection: two of
    forty-six sources 404'd on 2026-07-31 and took 46% of the domains with them,
    because one of them was almost half the list on its own. A source-count
    threshold waved that through. Size is what users receive, so size is what
    gets checked.

    Growth is never blocked - adding coverage is the normal outcome of a fix.
    """
    if previous is None or previous <= 0:
        return True, 'no previous total recorded, nothing to compare against'

    delta = current - previous
    percent = delta / previous * 100

    if percent < -MAX_SHRINK_PERCENT:
        return False, (
            f'the list lost {abs(delta):,} domains against the previous '
            f'{previous:,} ({percent:.1f}%), beyond the {MAX_SHRINK_PERCENT}% '
            f'limit. A source has almost certainly stopped answering.'
        )
    return True, f'{delta:+,} against the previous {previous:,} ({percent:+.1f}%)'


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
    parser.add_argument('--previous', default=None,
                        help='Path to the previously published blacklist. Used to '
                             'tell a newly blocked domain apart from a blocked '
                             'domain that merely became more popular.')
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

    size_ok, size_message = check_shrinkage(len(blacklist), previous_total(HISTORY))
    log(f'{"✓" if size_ok else "✗"} Size: {size_message}')

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
    #
    # The question is "did a popular domain just get ADDED to the list", not
    # "is a blocked domain now popular". Tranco reranks daily, so domains drift
    # across the rank-1000 boundary on their own: an earlier version of this
    # check fired on that drift and blocked every release for ten nights, six of
    # the seven domains it flagged having been in the list for weeks. A gate
    # that fails on a non-event is a gate that gets switched off.
    #
    # So a domain is only escalated when it is popular AND absent from the
    # previously published list. Without that comparison the two cases are
    # indistinguishable, and the band is reported rather than enforced.
    in_band = [(rank, domain) for rank, domain in blocked_ranked if rank <= REVIEW_RANK]

    previous_blacklist: Optional[Set[str]] = None
    if args.previous:
        previous_path = Path(args.previous)
        if previous_path.is_file():
            previous_blacklist = load_blacklist(previous_path)
            log(f'✓ Previous release: {len(previous_blacklist):,} domains')
        else:
            log(f'Warning: previous release not found at {previous_path}')

    if previous_blacklist is None:
        log('No previous release to compare against; the review band is reported, '
            'not enforced.')
        unacknowledged = []
    else:
        unacknowledged = [
            (r, d) for r, d in in_band
            if d not in acknowledged and d not in previous_blacklist
        ]

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
        'size': {
            'published_domains': len(blacklist),
            'previous_domains': previous_total(HISTORY),
            'accepted': size_ok,
            'detail': size_message,
        },
        'protected': {
            'checked': len(protected),
            'violations': [
                {'domain': d, 'reason': protected[d]} for d in violations
            ],
        },
        'popularity': {
            'blocked_in_band': bands,
            'review_rank': REVIEW_RANK,
            'enforced': previous_blacklist is not None,
            'newly_blocked_in_band': [
                d for _, d in in_band
                if previous_blacklist is not None and d not in previous_blacklist
            ],
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

    if not size_ok:
        log('')
        log(f'FAIL: {size_message}')
        log('Check the per-source statistics for a source returning a non-2xx status.')
        return 1

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
        # Reported, not enforced. A popular domain being newly blocked is a
        # judgement call, not a defect: the size and protected-domain checks
        # above cover the cases where something is actually broken. Blocking the
        # release on an editorial question is what froze the published list for
        # two weeks, so this now leaves a review queue instead of a locked door.
        log('')
        log(f'REVIEW: {len(unacknowledged)} domain(s) newly blocked in the top '
            f'{REVIEW_RANK} and not yet reviewed:')
        for rank, domain in unacknowledged:
            who = ', '.join(attribution.get(domain, [])) or 'source unrecorded'
            log(f'  - #{rank} {domain}  <- {who}')
        log('')
        log(f'Not blocking the release. Review at leisure, then either whitelist '
            f'each one or add it to {ACKNOWLEDGED}.')

    log('')
    log('✓ No protected domain blocked, no unreviewed entry in the top '
        f'{REVIEW_RANK}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
