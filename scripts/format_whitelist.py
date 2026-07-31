#!/usr/bin/env python3
"""
Normalise whitelist.txt without discarding what it says.

The whitelist used to be tidied by a shell loop that validated every line
against an FQDN regex and kept only the lines that matched. Once entries carried
a trailing comment recording why they exist, none of them matched, and the run
deleted 384 entries - every entry that was actively holding a source back,
including a DNS resolver and a CDN apex. The file that exists to stop breakage
was silently emptied of exactly its load-bearing half.

So: comments are data here, not noise. This normaliser lowercases and sorts the
domains, drops duplicates and rejects malformed entries, while preserving the
leading header block and every trailing comment attached to an entry.

An entry is only ever dropped when its domain is genuinely malformed, and every
drop is reported on stderr so it appears in the workflow log rather than being
absorbed silently.

Run: python3 scripts/format_whitelist.py [--check]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

WHITELIST = Path('whitelist.txt')

# Same shape the pipeline requires: dot-separated labels, no leading or trailing
# hyphen, an alphabetic TLD.
FQDN = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$')
TLD = re.compile(r'^[a-z]{2,}$')


def is_valid_domain(domain: str) -> bool:
    if not FQDN.match(domain):
        return False
    return bool(TLD.match(domain.rsplit('.', 1)[-1]))


def split_entry(line: str) -> Tuple[str, Optional[str]]:
    """Split a line into its domain and its comment, either of which may be empty."""
    domain, sep, comment = line.partition('#')
    return domain.strip(), (comment.strip() if sep else None)


def format_whitelist(text: str) -> Tuple[str, List[str]]:
    """Return the normalised file and the entries that had to be dropped."""
    lines = text.splitlines()

    # The header is the comment block at the top of the file, kept verbatim and
    # in order: it documents the format that everything below depends on.
    header: List[str] = []
    index = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            header.append(line.rstrip())
        else:
            break
    else:
        index = len(lines)

    while header and not header[-1].strip():
        header.pop()

    entries = {}
    dropped: List[str] = []

    for line in lines[index:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            # A comment between entries has lost whatever it annotated; keeping
            # it would attach it to an unrelated domain after sorting.
            dropped.append(f'{stripped}  (free-standing comment)')
            continue

        domain, comment = split_entry(stripped)
        domain = domain.lower()

        if not domain:
            continue
        if not is_valid_domain(domain):
            dropped.append(f'{stripped}  (not a valid domain)')
            continue

        # On a duplicate, keep whichever copy carries an explanation.
        existing = entries.get(domain)
        if existing is None or (comment and not existing):
            entries[domain] = comment

    body = [
        f'{domain}  # {comment}' if comment else domain
        for domain, comment in sorted(entries.items())
    ]

    parts = []
    if header:
        parts.append('\n'.join(header))
        parts.append('')
    parts.append('\n'.join(body))

    return '\n'.join(parts) + '\n', dropped


def main() -> int:
    parser = argparse.ArgumentParser(description='Normalise whitelist.txt')
    parser.add_argument('--path', default=str(WHITELIST))
    parser.add_argument('--check', action='store_true',
                        help='Report whether the file is already normalised')
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f'FAIL: {path} not found', file=sys.stderr)
        return 1

    original = path.read_text(encoding='utf-8')
    formatted, dropped = format_whitelist(original)

    for entry in dropped:
        print(f'dropped: {entry}', file=sys.stderr)

    entries = sum(
        1 for line in formatted.splitlines()
        if line.strip() and not line.strip().startswith('#')
    )
    print(f'{entries} entries, {len(dropped)} dropped')

    if args.check:
        if formatted != original:
            print('FAIL: whitelist.txt is not normalised. Run: '
                  'python3 scripts/format_whitelist.py', file=sys.stderr)
            return 1
        print('OK: whitelist.txt is normalised')
        return 0

    if formatted != original:
        path.write_text(formatted, encoding='utf-8')
        print(f'✓ Rewrote {path}')
    else:
        print(f'{path} already normalised')

    return 0


if __name__ == '__main__':
    sys.exit(main())
