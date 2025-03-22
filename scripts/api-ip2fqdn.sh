#!/bin/bash

while read -r ip; do
      # Check if IP is valid
      if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        response=$(curl -s --max-time 3 "https://api-ipres.domainsblacklists.com/resolve/$ip")

        # Check if the response is valid JSON and contains the key 'fqdn'
        if echo "$response" | jq '.fqdn' &>/dev/null; then
          fqdn=$(echo "$response" | jq -r '.fqdn')

          # Remove trailing dot and append to the output file
          echo "${fqdn%.}" >> ip_blacklist_1.resolved.txt
        else
          echo "Failed to resolve IP: $ip or invalid response received"
        fi
      fi
    done < ip_blacklist_1.txt
