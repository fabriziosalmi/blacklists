import os
from pathlib import Path
import argparse
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_fqdn_from_file(file_path: Path) -> set:
    """Read the file and return a set of FQDNs."""
    try:
        with file_path.open('r', encoding='utf-8') as file:
            fqdns = {line.strip() for line in file if line.strip()}
            logging.debug(f"Read {len(fqdns)} FQDNs from {file_path}")
            if fqdns:
                logging.debug(f"Sample FQDNs from {file_path}: {list(fqdns)[:5]}")
            return fqdns
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        raise
    except PermissionError:
        logging.error(f"Permission denied: {file_path}")
        raise
    except IOError as e:
        logging.error(f"Error reading file {file_path}: {e}")
        raise

def write_fqdn_to_file(file_path: Path, content: set) -> None:
    """Write a set of FQDNs to the specified file."""
    try:
        with file_path.open('w', encoding='utf-8') as file:
            for fqdn in sorted(content):
                file.write(f"{fqdn}\n")
        logging.info(f"Filtered FQDNs written to {file_path} ({len(content)} entries).")
    except PermissionError:
        logging.error(f"Permission denied: {file_path}")
        raise
    except IOError as e:
        logging.error(f"Error writing file {file_path}: {e}")
        raise

def main(blacklist_path: Path, whitelist_path: Path, output_path: Path) -> None:
    """Main function to process blacklist and whitelist files."""
    start_time = time.time()
    
    try:
        blacklist_fqdns = read_fqdn_from_file(blacklist_path)
        whitelist_fqdns = frozenset(read_fqdn_from_file(whitelist_path))  # Optimized for set lookup

        filtered_fqdns = blacklist_fqdns - whitelist_fqdns
        write_fqdn_to_file(output_path, filtered_fqdns)

        logging.info(f"Blacklist: {len(blacklist_fqdns)} FQDNs.")
        logging.info(f"Whitelist: {len(whitelist_fqdns)} FQDNs.")
        logging.info(f"After Filtering: {len(filtered_fqdns)} FQDNs.")
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        exit(1)
    
    logging.info(f"Processing complete. Time taken: {time.time() - start_time:.2f} seconds")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process blacklist and whitelist files.")
    parser.add_argument('--blacklist', default='blacklist.txt', type=Path, help='Path to blacklist file')
    parser.add_argument('--whitelist', default='whitelist.txt', type=Path, help='Path to whitelist file')
    parser.add_argument('--output', default='filtered_blacklist.txt', type=Path, help='Path to output file')
    
    args = parser.parse_args()
    main(args.blacklist, args.whitelist, args.output)
