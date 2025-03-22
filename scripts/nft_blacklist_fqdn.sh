#!/bin/bash

print_error() {
  echo "Error: $1" >&2
  exit 1
}

print_success() {
  echo "Success: $1"
}

validate_domain() {
  local domain="$1"
  local domain_regex="^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,63}$"
  [[ ! "$domain" =~ $domain_regex ]] && print_error "Invalid domain name: $domain"
}

readonly BLACKLIST_URL="https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt"
readonly INPUT_FILE="/tmp/all.fqdn.blacklist"
readonly RULES_FILE="nftables_rules.nft"
readonly TABLE_NAME="filter"
readonly CHAIN_NAME="input_drop"

if ! wget -q -O "$INPUT_FILE" "$BLACKLIST_URL"; then
  print_error "Failed to download the blacklist from $BLACKLIST_URL"
fi

[[ ! -r "$INPUT_FILE" ]] && print_error "Input file not found or not readable: $INPUT_FILE"

{
  echo "#!/usr/sbin/nft -f"
  echo "flush ruleset"
  echo "table $TABLE_NAME {"
  echo "    chain $CHAIN_NAME {"

  while IFS= read -r domain || [[ -n "$domain" ]]; do
    validate_domain "$domain"
    echo "        drop ip daddr $domain"
    echo "        drop ip saddr $domain"
  done < "$INPUT_FILE"

  echo "    }"
  echo "}"
} > "$RULES_FILE"

nft -f "$RULES_FILE" || print_error "Error applying nftables rules. Ensure you have the necessary privileges."

rm -f "$INPUT_FILE" "$RULES_FILE"
