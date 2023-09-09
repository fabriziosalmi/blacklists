import re
import tldextract
from tqdm import tqdm

# Pre-compiled regex pattern for FQDN validation
fqdn_pattern = re.compile('^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')

def is_valid_fqdn(s):
    """Check if the string is a valid FQDN."""
    if '*' in s or not s:
        return False
    extracted = tldextract.extract(s)
    if not all([extracted.domain, extracted.suffix]):
        return False
    return all(fqdn_pattern.match(x) for x in s.split('.'))

def remove_prefix(line, prefix):
    """General function to remove specified prefix from a line."""
    if line.startswith(prefix):
        potential_fqdn = line[len(prefix):]
        if is_valid_fqdn(potential_fqdn):
            return potential_fqdn
    return line

def sanitize_line(line, rules):
    """Apply all sanitization rules to a line."""
    for rule in rules:
        line = rule(line.strip())
        if line is None:
            return None
    return line

def get_sanitization_rules():
    """Returns a list of sanitization rules."""
    return [
        lambda line: None if line.startswith("#") else line,       # Remove comment lines
        lambda line: remove_prefix(line, "127.0.0.1"),             # Remove IP prefix 127.0.0.1 without space
        lambda line: remove_prefix(line, "127.0.0.1 "),            # Remove IP prefix 127.0.0.1 with space
        lambda line: remove_prefix(line, "0.0.0.0"),               # Remove IP prefix 0.0.0.0 without space
        lambda line: remove_prefix(line, "0.0.0.0 "),              # Remove IP prefix 0.0.0.0 with space
        lambda line: remove_prefix(line, "||"),                    # Remove double pipes
        lambda line: remove_prefix(line, "http://"),               # Remove http prefix
        lambda line: remove_prefix(line, "https://"),              # Remove https prefix
        lambda line: line.rstrip('.'),                             # Remove trailing dot
        lambda line: line.lower()                                  # Convert to lowercase
    ]

def process_large_file(input_file_path, output_file_path):
    """Process large files line by line."""
    unique_domains = set()
    rules = get_sanitization_rules()

    with open(input_file_path, 'r') as infile:
        total_lines = sum(1 for _ in infile)
        infile.seek(0)  # Reset file pointer to start
        for line in tqdm(infile, total=total_lines, desc="Processing"):
            sanitized_line = sanitize_line(line, rules)
            if sanitized_line and is_valid_fqdn(sanitized_line):
                unique_domains.add(sanitized_line)

    # Sort the unique domain names in alphabetical order
    sorted_unique_domains = sorted(unique_domains)

    # Write the sorted unique domain names to the output file
    with open(output_file_path, 'w') as outfile:
        for domain in tqdm(sorted_unique_domains, desc="Writing"):
            outfile.write(domain + '\n')

# Use this function to process your large file
process_large_file('input.txt', 'output.txt')
