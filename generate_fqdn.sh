#!/bin/bash

# Constants
readonly BLACKLIST_URL_FILE="blacklists.fqdn.urls"
readonly AGGREGATED_LIST="aggregated.fqdn.list"
readonly BLACKLIST_OUTPUT="all.fqdn.blacklist"
readonly COMPRESSED_BLACKLIST="all.fqdn.blacklist.tar.gz"
readonly REQUIRED_PACKAGES=(pv ncftp python3)

# Error Handling
trap 'echo "An error occurred. Exiting."; exit 1' ERR

setup_environment() {
    echo "Setting up the environment..."

    # Detect package manager
    if command -v apt-get &>/dev/null; then
        PACKAGE_MANAGER="apt-get"
        UPDATE_CMD="sudo apt-get update"
        INSTALL_CMD="sudo apt-get install -y"
    else
        echo "Unsupported package manager. Exiting."
        exit 1
    fi

    # Update and install prerequisites
    $UPDATE_CMD
    $INSTALL_CMD "${REQUIRED_PACKAGES[@]}"

    # Link python3 to python (for Ubuntu)
    if ! command -v python &>/dev/null; then
        sudo ln -s /usr/bin/python3 /usr/bin/python
    fi

    python3 -m ensurepip --upgrade
    pip3 install --no-cache-dir --upgrade pip setuptools tldextract tqdm
}

download_blacklists() {
    echo "Downloading blacklists..."

    while IFS= read -r url; do
        local random_filename=$(uuidgen | tr -dc '[:alnum:]')
        if ! wget -q --progress=bar:force -O "$random_filename.fqdn.list" "$url"; then
            echo "Failed to download: $url"
        fi
    done < "$BLACKLIST_URL_FILE"
}

aggregate_blacklists() {
    echo "Aggregating blacklists..."

    cat *.fqdn.list | sort -u > "$BLACKLIST_OUTPUT"
    rm -f *.fqdn.list
}

sanitize_blacklists() {
    echo "Sanitizing blacklists..."
    local temp_file
    temp_file=$(mktemp)
    python sanitize.py < "$BLACKLIST_OUTPUT" > "$temp_file"

    echo "Removing whitelisted domains..."
    python whitelist.py < "$temp_file" > "$BLACKLIST_OUTPUT"

    rm "$temp_file"
}

create_compressed_file() {
    echo "Compressing blacklist file..."

    tar -czf "$COMPRESSED_BLACKLIST" "$BLACKLIST_OUTPUT" || {
        echo "Error: Failed to create the tar.gz file."
        exit 1
    }

    total_lines_new=$(wc -l < "$BLACKLIST_OUTPUT")
    echo "Total domains: $total_lines_new."
}

# Execute functions
setup_environment
download_blacklists
aggregate_blacklists
sanitize_blacklists
create_compressed_file
