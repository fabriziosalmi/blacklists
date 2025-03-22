#!/bin/bash

# Script to check domain against API

# Ensure curl is installed
if ! command -v curl &> /dev/null; then
    echo "Error: curl command not found."
    exit 1
fi

# Ensure a domain is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 domain.com"
    exit 1
fi

API_URL="https://check.domainsblacklists.com/check_domain"
API_UA="DomainsBlacklists"

# Send request to the API
response=$(curl -s -H "User-Agent: $API_UA" -X POST -H "Content-Type: application/json" -d "{\"domains\": [\"$1\"]}" $API_URL)

# Print the response
echo "$response" | jq '.'  # Use jq to pretty-print JSON response

# If jq isn't installed, fall back to just echoing the raw response:
if [ $? -ne 0 ]; then
    echo "Tip: Install 'jq' for a better formatted output."
    echo "$response"
fi
