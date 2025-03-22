#!/bin/bash

# Input file containing blacklisted FQDNs (one per line)
input_file="blacklist.txt"

# Output Unbound configuration file
output_file="unbound-domainsblacklists.com.conf"

# Check if the input file exists
if [ ! -f "$input_file" ]; then
    echo "Error: Input file '$input_file' not found."
    exit 1
fi

# Create or overwrite the output file
> "$output_file"

# Unbound local-zone configuration
local_zone_config="server:\n"

# Loop through each line in the input file
while IFS= read -r line; do
    # Remove leading and trailing whitespace using the trim function
    domain=$(trim "$line")

    # Check if the line is empty or starts with a comment character (#)
    if [[ -n "$domain" && ! "$domain" =~ ^# ]]; then
        # Add the domain to the local-zone configuration
        local_zone_config+="    local-zone: \"$domain\" refuse\n"
    fi
done < "$input_file"

# Append the local-zone configuration to the output file
echo -e "$local_zone_config" >> "$output_file"

# Check if the output file was created successfully
if [ -f "$output_file" ]; then
    echo "Unbound blacklist configuration generated in $output_file."
else
    echo "Error: Failed to generate the Unbound blacklist configuration."
fi

# Function to remove leading and trailing whitespace
trim() {
    local str="$1"
    str="${str#"${str%%[![:space:]]*}"}"   # remove leading whitespace
    str="${str%"${str##*[![:space:]]}"}"   # remove trailing whitespace
    echo "$str"
}
