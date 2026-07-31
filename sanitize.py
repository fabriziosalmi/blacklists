import re
import tldextract
from tqdm import tqdm
from typing import Set, List, Callable, Optional
from functools import lru_cache
import multiprocessing as mp
from itertools import islice
import mmap
import os

# Pre-compiled regex pattern for FQDN validation (kept exactly as original)
FQDN_PATTERN = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')

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
    """Reduce an Adblock domain anchor to a bare domain.

    ``||example.com^`` and ``||example.com^$third-party`` both denote the
    domain ``example.com``. Anything carrying a path, wildcard or element-hiding
    separator is not a plain domain rule and cannot be expressed in a domain
    list, so it is dropped instead of being mangled into a bogus entry.
    """
    if not line.startswith("||"):
        return line

    line = line[2:]
    # Cut the rule terminator and any modifiers that follow it.
    line = line.split("^")[0].split("$")[0]

    # A path-scoped rule blocks one URL, not the host. Widening it to the whole
    # domain would block traffic the upstream author never intended to block, so
    # such rules are dropped: a DNS-level list cannot express them.
    if "/" in line:
        return None

    # Wildcards and element-hiding rules have no domain-list equivalent.
    if not line or "*" in line or "#" in line or "=" in line:
        return None
    return line

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

def process_large_file(input_file_path: str, output_file_path: str, chunk_size: int = 50000):
    """
    Process large files using memory mapping and multiprocessing.
    
    Args:
        input_file_path: Path to input file
        output_file_path: Path to output file
        chunk_size: Number of lines to process in each chunk
    """
    # Get number of CPU cores (leave one core free for system processes)
    num_processes = max(1, mp.cpu_count() - 1)
    
    try:
        file_size = get_file_size(input_file_path)
        unique_domains: Set[str] = set()
        
        # Use memory mapping for efficient file reading
        with open(input_file_path, 'r') as infile:
            mm = mmap.mmap(infile.fileno(), 0, access=mmap.ACCESS_READ)
            
            # Create process pool
            with mp.Pool(num_processes) as pool:
                # Process file in chunks
                chunks = []
                current_chunk = []
                
                # Use tqdm to show progress
                with tqdm(total=file_size, desc="Reading file") as pbar:
                    for line in iter(mm.readline, b""):
                        try:
                            decoded_line = line.decode('utf-8')
                            current_chunk.append(decoded_line)
                            
                            if len(current_chunk) >= chunk_size:
                                chunks.append(current_chunk)
                                current_chunk = []
                                
                            pbar.update(len(line))
                        except UnicodeDecodeError:
                            continue
                
                # Add remaining lines
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Process chunks in parallel
                with tqdm(total=len(chunks), desc="Processing chunks") as pbar:
                    for result in pool.imap_unordered(process_chunk, chunks):
                        unique_domains.update(result)
                        pbar.update(1)
        
        # Sort the unique domain names in alphabetical order (kept exactly as original)
        sorted_unique_domains = sorted(unique_domains)
        
        # Write results in batches
        batch_size = 10000
        with open(output_file_path, 'w') as outfile:
            with tqdm(total=len(sorted_unique_domains), desc="Writing results") as pbar:
                for i in range(0, len(sorted_unique_domains), batch_size):
                    batch = sorted_unique_domains[i:i + batch_size]
                    outfile.writelines(f"{domain}\n" for domain in batch)
                    pbar.update(len(batch))
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
