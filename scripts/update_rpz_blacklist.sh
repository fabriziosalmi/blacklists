#!/bin/bash

# ==========================================
# RPZ BLACKLIST UPDATER SCRIPT
# ==========================================

# List of required commands
REQUIRED_COMMANDS=("wget" "tar" "systemctl" "grep" "mkdir" "cat" "date" "named-checkconf")

# Check if required commands are installed
for cmd in "${REQUIRED_COMMANDS[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: $cmd is required but not installed. Exiting."
    exit 1
  fi
done

# Directory to store the RPZ blacklist
RPZ_DIRECTORY="/path/to/store/rpz_blacklist"
# URL of the RPZ blacklist
RPZ_URL="https://github.com/fabriziosalmi/blacklists/raw/main/rpz_blacklist.tar.gz"
# BIND configuration file
BIND_CONFIG="/etc/bind/named.conf.local"

# Ensure the directory for the RPZ blacklist exists
mkdir -p "$RPZ_DIRECTORY"

# Download the latest RPZ blacklist from the repository
wget -O "$RPZ_DIRECTORY/rpz_blacklist.tar.gz" "$RPZ_URL"

# Extract the blacklist
tar -xzf "$RPZ_DIRECTORY/rpz_blacklist.tar.gz" -C "$RPZ_DIRECTORY"

# Check if the configuration is already added to avoid duplicate entries
if ! grep -q "rpz.blacklist" "$BIND_CONFIG"; then
    # Append configuration to BIND's config file
    echo "zone \"rpz.blacklist\" {
        type master;
        file \"$RPZ_DIRECTORY/rpz_blacklist.txt\";
    };" >> "$BIND_CONFIG"

    echo "options {
        response-policy { zone \"rpz.blacklist\"; };
    };" >> "$BIND_CONFIG"
fi

# Check BIND configuration
if ! named-checkconf "$BIND_CONFIG"; then
    echo "Error in BIND configuration. Please check manually!"
    exit 1
fi

echo "Script executed successfully!"

# To manually reload BIND and apply the new blacklist:
# sudo systemctl reload bind9
# You can also schedule this script using cron for automation.
# For example, to run it daily at 2 AM:
# crontab -e
# Add:
# 0 2 * * * /path/to/this_script/update_rpz_blacklist.sh
