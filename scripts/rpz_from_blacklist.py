#!/usr/bin/env python3
"""Build the RPZ zone file, dropping entries that cannot be owner names in it.

A response policy zone is a DNS zone, and every entry becomes an owner name
RELATIVE to the origin. DNS limits an encoded name to 255 octets: one length
byte per label, plus the label bytes, plus the root label. An entry that is a
perfectly valid domain on its own can therefore exceed the limit once the origin
is appended, and `named-checkzone` then refuses the WHOLE zone with

    dns_master_load: <file>:<line>: ran out of space

which protects nobody, because the artifact simply does not ship.

That is not hypothetical. The list aggregates roughly six million domains from
43 third-party feeds, and on 2026-09-10 one of them carried a 249-character,
17-label name whose encoded length with the origin `rpz.blacklist` is 265. One
upstream entry, and the entire daily release stops.

`sanitize.is_valid_fqdn` does not catch it: it checks each label against a
pattern and never measures the name as a whole, let alone in the zone it will
live in. Neither did anything else, because until 2026-09-10 the RPZ was emitted
by a bare `awk` with no SOA, no NS and no verification, so the published file was
never a loadable zone in the first place.

A name over the limit cannot be queried by any resolver, so dropping it costs no
protection: nothing could ever have asked for it.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# RFC 1035 2.3.4: 255 octets for the encoded name, root label included.
MAX_ENCODED_NAME = 255

# A handful of over-long entries is one bad feed row. Hundreds means an upstream
# format changed and we are about to silently discard real blocking rules, which
# is worse than failing.
DEFAULT_MAX_DROPPED = 25


def encoded_length(name: str, origin: str) -> int:
    """Octets the name occupies on the wire once placed under `origin`."""
    labels = [label for label in (name.split('.') + origin.split('.')) if label]
    return sum(1 + len(label) for label in labels) + 1


def fits(name: str, origin: str) -> bool:
    return encoded_length(name, origin) <= MAX_ENCODED_NAME


def build(source: Path, out: Path, origin: str, serial: str) -> tuple[int, list[str]]:
    """Write the zone. Returns (kept, dropped entries)."""
    dropped: list[str] = []
    kept = 0
    with source.open(encoding='utf-8', errors='replace') as src, \
            out.open('w', encoding='utf-8') as dst:
        dst.write(
            '; Aggregated by fabriziosalmi/blacklists from multiple third-party\n'
            '; sources under their respective licenses - see SOURCES.md\n'
            '; https://github.com/fabriziosalmi/blacklists/blob/main/SOURCES.md\n'
            f'; Generated: {datetime.now(timezone.utc):%Y-%m-%d} UTC\n'
            ';\n'
            '$TTL 60\n'
            f'@ IN SOA localhost. root.localhost. ( {serial} 3600 600 604800 60 )\n'
            '@ IN NS  localhost.\n'
        )
        for line in src:
            entry = line.strip()
            if not entry or entry.startswith('#'):
                continue
            if not fits(entry, origin):
                dropped.append(entry)
                continue
            dst.write(entry + ' CNAME .\n')
            kept += 1
    return kept, dropped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--blacklist', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--origin', default='rpz.blacklist')
    ap.add_argument('--serial', default=None)
    ap.add_argument('--max-dropped', type=int, default=DEFAULT_MAX_DROPPED)
    args = ap.parse_args(argv)

    if not args.blacklist.is_file():
        print(f'FAIL: {args.blacklist} not found', file=sys.stderr)
        return 1

    serial = args.serial or f'{datetime.now(timezone.utc):%Y%m%d%H}'
    kept, dropped = build(args.blacklist, args.out, args.origin, serial)

    print(f'RPZ: {kept:,} entries under origin {args.origin}')
    if dropped:
        limit = MAX_ENCODED_NAME - encoded_length('', args.origin)
        print(f'RPZ: dropped {len(dropped)} entry(ies) too long to be an owner '
              f'name here (over {limit} octets of labels under {args.origin}):')
        for entry in dropped[:10]:
            print(f'      {encoded_length(entry, args.origin)} octets  {entry[:100]}')
        if len(dropped) > 10:
            print(f'      ... and {len(dropped) - 10} more')

    if len(dropped) > args.max_dropped:
        print(f'FAIL: {len(dropped)} entries dropped, over the {args.max_dropped} '
              f'allowed. That is an upstream format change, not a stray row: '
              f'fix the source rather than discarding real blocking rules.',
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
