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
    elif [[ "$(uname -s)" == "Darwin" ]]; then  # macOS check
        PACKAGE_MANAGER="brew"
        UPDATE_CMD="brew update"
        INSTALL_CMD="brew install"
    else
        echo "Unsupported package manager. Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi
}

# Update and install prerequisites
update_and_install() {
    echo "Updating system and installing Python 3..." | tee -a "$LOGFILE"
    $UPDATE_CMD | tee -a "$LOGFILE"

    if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
       $INSTALL_CMD python3  | tee -a "$LOGFILE"
    else
        $INSTALL_CMD python3 | tee -a "$LOGFILE"
        if [ "$PACKAGE_MANAGER" == "apt-get" ]; then
            sudo ln -sf /usr/bin/python3 /usr/bin/python
        fi
    fi

    # Check if python3-pip is installed; install if necessary.
    if ! command -v pip3 &>/dev/null; then
        echo "pip3 not found, installing..." | tee -a "$LOGFILE"
        if [[ "$PACKAGE_MANAGER" == "apt-get" ]]; then
            $INSTALL_CMD python3-pip | tee -a "$LOGFILE"
        else
           echo "No pip package found for your package manager. Please install pip manually. Exiting ❌." | tee -a "$LOGFILE"
           exit 1
        fi
    fi

    # Ensure pip and setuptools are up to date
    echo "Ensuring pip and setuptools are up to date..." | tee -a "$LOGFILE"
    python3 -m ensurepip --upgrade | tee -a "$LOGFILE"
    pip3 install --no-cache-dir --upgrade pip setuptools tldextract tqdm | tee -a "$LOGFILE"
}

# Install additional required packages
install_additional_packages() {
    local packages="pv ncftp"

    # Handle macOS with brew differently: pv is coreutils, ncftp might not be available
    if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
        packages="coreutils wget" # coreutils includes pv on macOS

        # Try installing ncftp, but don't fatally fail if it's not found
        if ! $INSTALL_CMD ncftp | tee -a "$LOGFILE" 2>&1; then
          echo "ncftp not found on brew. Proceeding without it (Optional Package)." | tee -a "$LOGFILE"
          NCFTP_INSTALLED=false
        else
          NCFTP_INSTALLED=true
        fi
    fi

    for package in $packages; do
        echo "Installing package: $package..." | tee -a "$LOGFILE"
        if ! $INSTALL_CMD $package | tee -a "$LOGFILE"; then
            echo "Failed to install '$package' using $PACKAGE_MANAGER ❌." | tee -a "$LOGFILE"
            exit 1
        fi
    done
}

# Directory holding one downloaded file per source, named by its position in
# blacklists.fqdn.urls. Deterministic names are what make per-source
# attribution possible later: with random names the aggregate cannot be traced
# back to the list that supplied each domain.
SOURCES_DIR="sources_raw"

# Download a single source and record the outcome.
#
# The HTTP status is captured rather than discarded, and only a 2xx response is
# handed to the aggregator. A source returning a 404 HTML error page must
# contribute nothing instead of contributing markup that later has to be
# filtered out by luck.
download_url() {
    local index="$1"
    local url="$2"
    local target="${SOURCES_DIR}/$(printf '%03d' "$index").fqdn.list"
    local meta="${SOURCES_DIR}/$(printf '%03d' "$index").meta"

    local start_ts=$(date +%s)
    local status
    status=$(curl -sSL \
        --max-time 120 \
        --retry 2 --retry-delay 3 \
        -A "fabriziosalmi-blacklists/1.0 (+https://github.com/fabriziosalmi/blacklists)" \
        -o "$target" \
        -w '%{http_code}' \
        "$url" 2>>"$LOGFILE") || status="000"
    local elapsed=$(( $(date +%s) - start_ts ))

    local bytes=0
    [ -f "$target" ] && bytes=$(wc -c < "$target" | tr -d ' ')

    # Record the outcome before deciding what to do with it, so a failure is
    # still reported to the statistics step.
    printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$url" "$status" "$bytes" "$elapsed" > "$meta"

    if [[ ! "$status" =~ ^2 ]]; then
        echo "Source $index returned HTTP $status, excluding from aggregate: $url ❌" | tee -a "$LOGFILE"
        rm -f "$target"
        return 1
    fi

    echo "Downloaded source $index (HTTP $status, ${bytes} bytes): $url" | tee -a "$LOGFILE"
}

# Download all URLs from the list and handle files
manage_downloads() {
    local LISTS="blacklists.fqdn.urls"
    if [ ! -f "$LISTS" ]; then
        echo "File $LISTS not found. Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi

    rm -rf "$SOURCES_DIR"
    mkdir -p "$SOURCES_DIR"

    echo "Starting downloads..." | tee -a "$LOGFILE"
    local index=0
    while IFS= read -r url; do
        # Skip blank lines and comments so indices line up with the URLs that
        # are actually fetched.
        case "$url" in ''|\#*) continue;; esac
        download_url "$index" "$url" &
        index=$((index + 1))
    done < "$LISTS"
    wait

    local downloaded
    downloaded=$(find "$SOURCES_DIR" -name '*.fqdn.list' | wc -l | tr -d ' ')
    echo "Downloaded ${downloaded}/${index} sources successfully." | tee -a "$LOGFILE"

    if [ "$downloaded" -eq 0 ]; then
        echo "No sources downloaded. Check network access and URLs. Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi

    # Refuse to build a release from a partial fetch: silently shipping a list
    # missing half its sources looks like a real update to every downstream user.
    local min_required=$(( index / 2 ))
    if [ "$downloaded" -lt "$min_required" ]; then
        echo "Only ${downloaded}/${index} sources downloaded (need at least ${min_required}). Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi

    echo "Aggregating blacklists..." | tee -a "$LOGFILE"
    local aggregated_file="aggregated.fqdn.list"
    cat "$SOURCES_DIR"/*.fqdn.list > "$aggregated_file"

    sort -u "$aggregated_file" > all.fqdn.blacklist

    # Check for an empty blacklist file after sort
    if [ ! -s "all.fqdn.blacklist" ]; then
      echo "all.fqdn.blacklist is empty after sort. Check input data and sort command. Exiting ❌" | tee -a "$LOGFILE"
      exit 1
    fi

    # The per-source files are deliberately kept: scripts/source_stats.py reads
    # them to attribute the aggregate. The caller removes them when done.
    rm -f "$aggregated_file"
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

# Prepend an attribution header to the aggregated blacklist. The published
# blacklist.txt redistributes many third-party lists under their own licenses,
# so the artifact itself documents its provenance (see SOURCES.md).
prepend_attribution_header() {
    local target="all.fqdn.blacklist"
    if [ ! -f "$target" ]; then
        echo "Cannot prepend header: $target not found. Skipping." | tee -a "$LOGFILE"
        return 0
    fi

    local domain_count
    domain_count=$(grep -Evc '^[[:space:]]*#' "$target" 2>/dev/null || wc -l < "$target")
    local gen_date
    gen_date=$(date -u '+%Y-%m-%d')

    local tmp="${target}.tmp"
    {
        echo "# Aggregated by fabriziosalmi/blacklists from multiple third-party sources under their respective licenses - see SOURCES.md"
        echo "# Generated: ${gen_date} UTC"
        echo "# Domains: ${domain_count}"
        echo "# Source lists: https://github.com/fabriziosalmi/blacklists/blob/main/blacklists.fqdn.urls"
        cat "$target"
    } > "$tmp" && mv "$tmp" "$target"

    echo "Prepended attribution header (${domain_count} domains)." | tee -a "$LOGFILE"
}

# Main routine
main() {
    detect_package_manager
    update_and_install
    install_additional_packages
    manage_downloads
    sanitize_and_whitelist
    prepend_attribution_header
    local total_lines_new=$(grep -Evc '^[[:space:]]*#' all.fqdn.blacklist 2>/dev/null || echo 0)
    echo "Total domains: $total_lines_new 🌍." | tee -a "$LOGFILE"
}

main