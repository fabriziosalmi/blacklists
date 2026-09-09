import re
import tldextract
from typing import Set, List, Callable, Iterator, Optional
from functools import lru_cache
import multiprocessing as mp
from itertools import islice
import os

# Pre-compiled regex pattern for FQDN validation (kept exactly as original)
FQDN_PATTERN = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')

# How many chunks may be outstanding per worker before the reader stops reading.
# This is the whole memory bound: without it the pool's task handler pulls the
# entire input onto its queue regardless of how lazily the chunks are produced.
MAX_PENDING_CHUNKS = 2

@lru_cache(maxsize=10000)
def is_valid_fqdn(s: str) -> bool:
    """Check if the string is a valid FQDN."""
    if '*' in s or not s:
        return False
    extracted = tldextract.extract(s)
    if not all([extracted.domain, extracted.suffix]):
        return False
    return all(FQDN_PATTERN.match(x) for x in s.split('.'))

def remove_prefixes(line: str, prefixes: List[str] = ["127.0.0.1", "0.0.0.0", "||", "http://", "https://"]) -> str:
    """Remove specified prefixes from a line."""
    for prefix in prefixes:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return line

def drop_metadata(line: str) -> Optional[str]:
    """Drop lines that carry no blocking rule, and lines that un-block.

    Adblock-syntax lists open with a ``[Adblock Plus]`` marker and ``!`` header
    comments, and use ``@@`` for EXCEPTION rules - entries the upstream author
    has explicitly decided must NOT be blocked. Treating an exception as a block
    would invert the author's intent, so those lines are discarded rather than
    parsed.
    """
    if not line or line.startswith(("#", "!", "[", "@@")):
        return None
    return line

def strip_adblock_syntax(line: str) -> Optional[str]:
    """Reduce an unconditional Adblock domain anchor to a bare domain.

    Only ``||example.com^`` is translatable to a domain list. Every other form
    means something a DNS blocklist cannot express, and converting it anyway
    produces a block the upstream author never asked for:

    * ``$`` modifiers make a rule conditional or cancel it outright.
      ``$badfilter`` DISABLES a matching rule, ``$doc`` shows a warning page in
      the browser rather than blocking, and ``$to=~cloudflare.net`` applies only
      to some destinations. Blocking on any of these inverts or over-applies the
      author's intent, so a rule carrying a modifier is dropped whatever the
      modifier is - there is no safe subset worth special-casing.
    * A path-scoped rule blocks one URL, not the host.
    * Wildcards and element-hiding rules have no domain-list equivalent.

    The modifier check runs before anything else is stripped: the separator
    preceding ``$`` is not always ``^`` (``||example.com.$all,to=~x`` ends the
    hostname with a dot), so splitting on ``^`` first would let those through.
    """
    if not line.startswith("||"):
        return line

    line = line[2:]

    if "$" in line:
        return None

    line = line.split("^")[0]

    if "/" in line:
        return None

    if not line or "*" in line or "#" in line or "=" in line:
        return None
    return line

# Adblock cosmetic separators, anchored to a bare domain rather than to "||":
# "##" (element hiding), "#@#" (its exception), "#?#" / "#$?#" (extended CSS),
# "#$#" (style/snippet) and "#%#" (AdGuard scriptlet), each optionally negated
# with "@". The separator is attached directly to the hostname, so it is only
# treated as cosmetic when nothing separates it from the domain - that is what
# keeps a genuine inline comment such as "example.com  ## note" out of scope.
COSMETIC_PATTERN = re.compile(r'(?<!\s)#@?[$%]?\??#')


def drop_cosmetic_rules(line: str) -> Optional[str]:
    """Drop Adblock cosmetic filters, which are the opposite of a block.

    ``example.com##.banner`` tells a browser extension to LOAD example.com and
    hide one element on it. It is not a blocking rule, and a domain list has no
    way to express it.

    This mattered because ``strip_adblock_syntax`` only inspects lines starting
    with ``||``, while cosmetic rules are anchored to a bare domain. Such a line
    therefore reached ``take_first_token``, which split it on ``#`` and kept the
    hostname - turning "hide a div on this site" into "NXDOMAIN this site".

    The published list carried ``pages.dev``, ``web.core.windows.net``,
    ``webflow.io`` and ``ondigitalocean.app`` as a result: shared-hosting apexes
    whose blocking takes down every unrelated site beneath them, and which the
    Unbound and RPZ outputs expand to the whole subtree. ``ublockorigin.com``
    was blocked by uBlock's own anti-impostor rule.

    Nothing is lost by dropping these: a cosmetic rule never asked for a block.
    """
    if not line:
        return None
    return None if COSMETIC_PATTERN.search(line) else line


def take_first_token(line: str) -> Optional[str]:
    """Keep the hostname from lines that carry trailing text.

    Covers hosts-file entries whose address prefix has already been removed and
    lists that append an inline comment, e.g. ``example.com #tracker``.
    """
    if not line:
        return None
    line = line.split("#")[0].split("!")[0]
    parts = line.split()
    return parts[0] if parts else None

def get_sanitization_rules() -> List[Callable]:
    """Returns a list of sanitization rules."""
    return [
        drop_metadata,                                             # Drop comments, headers and exception rules
        lambda line: remove_prefixes(line, ["127.0.0.1", "0.0.0.0", "http://", "https://"]),  # Remove prefixes
        strip_adblock_syntax,                                      # Reduce ||domain^ to domain
        drop_cosmetic_rules,                                       # Drop domain##selector and friends
        take_first_token,                                          # Drop trailing comments / hosts remainder
        lambda line: line.rstrip('.'),                             # Remove trailing dot
        lambda line: line.lower()                                  # Convert to lowercase
    ]

def sanitize_line(line: str, rules: List[Callable]) -> Optional[str]:
    """Apply all sanitization rules to a line."""
    for rule in rules:
        line = rule(line.strip())
        if line is None:
            return None
    return line

def process_chunk(chunk: List[str]) -> Set[str]:
    """Process a chunk of lines and return unique valid domains."""
    unique_domains = set()
    rules = get_sanitization_rules()
    
    for line in chunk:
        sanitized_line = sanitize_line(line, rules)
        if sanitized_line and is_valid_fqdn(sanitized_line):
            unique_domains.add(sanitized_line)
            
    return unique_domains

def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)


def iter_chunks(handle, chunk_size: int) -> Iterator[List[str]]:
    """Yield lists of at most ``chunk_size`` decoded lines, one at a time.

    Reads in binary and decodes per line so that an undecodable line is skipped
    rather than aborting the run, which is what the previous implementation did.
    """
    chunk: List[str] = []
    for raw in handle:
        try:
            chunk.append(raw.decode('utf-8'))
        except UnicodeDecodeError:
            continue
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def process_large_file(input_file_path: str, output_file_path: str, chunk_size: int = 50000):
    """Sanitize a large file in parallel, holding a bounded slice of it in memory.

    The previous version described itself as memory-mapped and chunked for
    exactly this reason, and then did the opposite: it read the whole file into
    a list of lists of Python strings BEFORE dispatching any work, so peak
    memory scaled with the input instead of being bounded by it. On a 150 MB
    aggregate that is several gigabytes of str objects, every one of which then
    had to be pickled to a worker. The mmap contributed nothing, because each
    line was decoded into a Python object anyway.

    Chunks are now produced lazily and dispatched in waves of at most
    ``MAX_PENDING_CHUNKS`` per worker. Pool.imap_unordered cannot provide this
    on its own: its task handler drains the whole input iterable onto the queue
    as fast as it can, so a generator alone would still buffer everything. The
    wave is what applies the backpressure.

    What remains proportional to the data is the output set, which is inherent:
    the result is the deduplicated, sorted set of domains.

    Args:
        input_file_path: Path to input file
        output_file_path: Path to output file
        chunk_size: Number of lines handed to a worker at a time
    """
    num_processes = max(1, mp.cpu_count() - 1)
    in_flight = num_processes * MAX_PENDING_CHUNKS

    try:
        unique_domains: Set[str] = set()
        lines_read = 0

        with open(input_file_path, 'rb') as infile:
            chunks = iter_chunks(infile, chunk_size)

            with mp.Pool(num_processes) as pool:
                while True:
                    wave = list(islice(chunks, in_flight))
                    if not wave:
                        break
                    lines_read += sum(len(c) for c in wave)

                    for result in pool.imap_unordered(process_chunk, wave):
                        unique_domains.update(result)

                    # A plain line rather than a progress bar: this runs in a
                    # non-interactive CI log, where a bar redraws into thousands
                    # of unreadable lines.
                    print(f"  {lines_read:,} lines read, "
                          f"{len(unique_domains):,} unique domains so far", flush=True)

        sorted_unique_domains = sorted(unique_domains)

        with open(output_file_path, 'w') as outfile:
            outfile.writelines(f"{domain}\n" for domain in sorted_unique_domains)

        print(f"✓ {lines_read:,} lines in, {len(sorted_unique_domains):,} domains out",
              flush=True)
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        raise

# Default behavior matches original script
if __name__ == "__main__":
    try:
        process_large_file('input.txt', 'output.txt')
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
