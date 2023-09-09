import os
from pathlib import Path
import argparse
from tqdm import tqdm

def read_fqdn_from_file(file_path: Path) -> set:
    """Read the file and return a set of FQDNs."""
    with file_path.open('r') as file:
        return {line.strip() for line in tqdm(file, desc=f"Reading {file_path}", unit="lines", leave=False) if line.strip()}

def write_fqdn_to_file(file_path: Path, content: set) -> None:
    """Write a set of FQDNs to the specified file."""
    with file_path.open('w') as file:
        file.write('\n'.join(content))

def ensure_file_exists(file_path: Path) -> None:
    """Check if a file exists or exit the program."""
    if not file_path.is_file():
        print(f"ERROR: File '{file_path}' not found.")
        exit(1)

def main(blacklist_path: Path, whitelist_path: Path, output_path: Path) -> None:
    """Main function to process blacklist and whitelist files."""
    
    # Check if files exist
    ensure_file_exists(blacklist_path)
    ensure_file_exists(whitelist_path)

    blacklist_fqdns = read_fqdn_from_file(blacklist_path)
    whitelist_fqdns = read_fqdn_from_file(whitelist_path)

    # Filter out whitelisted FQDNs from the blacklist
    filtered_fqdns = blacklist_fqdns - whitelist_fqdns

    write_fqdn_to_file(output_path, filtered_fqdns)

    print(f"Blacklist: {len(blacklist_fqdns)} FQDNs.")
    print(f"Whitelist: {len(whitelist_fqdns)} FQDNs.")
    print(f"After Filtering: {len(filtered_fqdns)} FQDNs.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process blacklist and whitelist files.")
    parser.add_argument('--blacklist', default='blacklist.txt', type=Path, help='Path to blacklist file')
    parser.add_argument('--whitelist', default='whitelist.txt', type=Path, help='Path to whitelist file')
    parser.add_argument('--output', default='filtered_blacklist.txt', type=Path, help='Path to output file')
    
    args = parser.parse_args()

    try:
        main(args.blacklist, args.whitelist, args.output)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
