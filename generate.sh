#!/bin/bash

LOGFILE="setup_script.log"
echo "Setup script 🛠️" | tee -a "$LOGFILE"

# Detect package manager and configure commands for package operations
detect_package_manager() {
    if command -v apt-get &>/dev/null; then
        PACKAGE_MANAGER="apt-get"
        UPDATE_CMD="sudo apt-get update"
        INSTALL_CMD="sudo apt-get install -y"
    elif command -v apk &>/dev/null; then
        PACKAGE_MANAGER="apk"
        UPDATE_CMD="sudo apk update"
        INSTALL_CMD="sudo apk add --no-cache"
    else
        echo "Unsupported package manager. Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi
}

# Update and install prerequisites
update_and_install() {
    echo "Updating system and installing Python 3..." | tee -a "$LOGFILE"
    $UPDATE_CMD | tee -a "$LOGFILE"
    $INSTALL_CMD python3 | tee -a "$LOGFILE"
    if [ "$PACKAGE_MANAGER" == "apt-get" ]; then
        sudo ln -sf /usr/bin/python3 /usr/bin/python
    fi
    python3 -m ensurepip --upgrade | tee -a "$LOGFILE"
    pip3 install --no-cache-dir --upgrade pip setuptools tldextract tqdm | tee -a "$LOGFILE"
}

# Install additional required packages
install_additional_packages() {
    for package in pv ncftp; do
        echo "Installing package: $package..." | tee -a "$LOGFILE"
        if ! $INSTALL_CMD $package | tee -a "$LOGFILE"; then
            echo "Failed to install '$package' using $PACKAGE_MANAGER ❌." | tee -a "$LOGFILE"
            exit 1
        fi
    done
}

# Function to download a URL and save to a randomly named file
download_url() {
    local url="$1"
    local random_filename=$(uuidgen | tr -dc '[:alnum:]')
    echo "Downloading blacklist: $url -> $random_filename.fqdn.list" | tee -a "$LOGFILE"
    if ! wget -q --progress=bar:force -O "$random_filename.fqdn.list" "$url"; then
        echo "Failed to download: $url ❌" | tee -a "$LOGFILE"
        return 1
    fi
}

# Download all URLs from the list and handle files
manage_downloads() {
    local LISTS="blacklists.fqdn.urls"
    if [ ! -f "$LISTS" ]; then
        echo "File $LISTS not found. Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi
    echo "Starting downloads..." | tee -a "$LOGFILE"
    while IFS= read -r url; do
        download_url "$url" &
    done < "$LISTS"
    wait
    echo "Aggregating blacklists..." | tee -a "$LOGFILE"
    echo "" > aggregated.fqdn.list
    for file in *.fqdn.list; do
        [ -f "$file" ] && cat "$file" >> aggregated.fqdn.list
    done
    sort -u aggregated.fqdn.list > all.fqdn.blacklist
    echo "Cleanup: removing source files..." | tee -a "$LOGFILE"
    rm -f ./*.fqdn.list aggregated.fqdn.list
}

# Sanitize and whitelist downloaded blacklists
sanitize_and_whitelist() {
    echo "Sanitizing blacklists..." | tee -a "$LOGFILE"
    mv all.fqdn.blacklist input.txt || exit 1
    if [ -f sanitize.py ]; then
        python sanitize.py | tee -a "$LOGFILE"
        mv output.txt all.fqdn.blacklist || exit 1
    else
        echo "sanitize.py not found. Skipping sanitation." | tee -a "$LOGFILE"
    fi
    echo "Removing whitelisted domains..." | tee -a "$LOGFILE"
    mv all.fqdn.blacklist blacklist.txt || exit 1
    if [ -f whitelist.py ]; then
        python whitelist.py | tee -a "$LOGFILE"
        mv filtered_blacklist.txt all.fqdn.blacklist || exit 1
    else
        echo "whitelist.py not found. Skipping whitelist filtering." | tee -a "$LOGFILE"
    fi
    rm -f blacklist.txt input.txt
}

# Main routine
main() {
    detect_package_manager
    update_and_install
    install_additional_packages
    manage_downloads
    sanitize_and_whitelist
    local total_lines_new=$(wc -l < all.fqdn.blacklist 2>/dev/null || echo 0)
    echo "Total domains: $total_lines_new 🌍." | tee -a "$LOGFILE"
}

main
