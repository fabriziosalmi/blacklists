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

# Check that the tools this script actually uses are present.
#
# This used to install "pv" and "ncftp", plus coreutils and wget on macOS, and
# had a whole branch for tolerating a missing ncftp. None of the four is used
# anywhere in this file - the downloads are curl and the aggregation is sort and
# grep - so every run spent time, and a sudo package install, on nothing, and
# could fail the build on a package it did not need.
check_required_tools() {
    local missing=""
    for tool in curl sort grep awk; do
        command -v "$tool" &>/dev/null || missing="$missing $tool"
    done

    if [ -n "$missing" ]; then
        echo "Missing required tools:$missing ❌." | tee -a "$LOGFILE"
        exit 1
    fi
    echo "Required tools present: curl, sort, grep, awk." | tee -a "$LOGFILE"
}

# Directory holding one downloaded file per source, named by its position in
# blacklists.fqdn.urls. Deterministic names are what make per-source
# attribution possible later: with random names the aggregate cannot be traced
# back to the list that supplied each domain.
SOURCES_DIR="sources_raw"

# Sources that are maintained inside this repository rather than upstream.
#
# These were being fetched from raw.githubusercontent.com, which made the build
# depend on GitHub's CDN to read a file two directories away on the same disk.
# That bought nothing and cost three things: the build could run against a
# cached copy that no longer matched the checkout it was building from, a rename
# or a CDN blip looked exactly like an upstream source going down, and the
# project appeared in its own credits as a third-party feed.
#
# The URL is kept as the identifier so sources/registry.json, source_stats.py
# and the published attribution keep working unchanged - only the fetch is local.
local_source_path() {
    case "$1" in
        https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/*)
            echo "${1#https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/}"
            ;;
    esac
}

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

    # Resolve a repository-local source from the checkout. Recorded with the
    # same meta shape as a fetch so the statistics step needs no special case.
    local local_path
    local_path=$(local_source_path "$url")
    if [ -n "$local_path" ]; then
        if [ ! -f "$local_path" ]; then
            echo "Local source $index is missing from the checkout: $local_path ❌" | tee -a "$LOGFILE"
            printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$url" "404" "0" "0" > "$meta"
            return 1
        fi
        cp "$local_path" "$target"
        local local_bytes
        local_bytes=$(wc -c < "$target" | tr -d ' ')
        printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$url" "200" "$local_bytes" "0" > "$meta"
        echo "Read local source $index (${local_bytes} bytes): $local_path" | tee -a "$LOGFILE"
        return 0
    fi

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

    # Some publishers ship a category as a tar.gz holding a "domains" file
    # rather than a flat list. Unpacking it here keeps one download path and one
    # meta record per source, and lets the registry point at the authoritative
    # endpoint instead of a re-publisher's flattened copy of it.
    #
    # The directory inside the archive is not always named after the category -
    # UT1's malware.tar.gz unpacks to phishing/ - so the member is matched by
    # glob and never by a path built from the URL.
    #
    # Extracting is not optional: handing sanitize.py a gzip blob would yield
    # zero domains from a source that answered HTTP 200, and losing one source's
    # worth of domains is well inside the release size gate's tolerance. It would
    # ship silently.
    if [[ "$url" == *.tar.gz ]]; then
        local unpacked="${target}.domains"
        # GNU tar and bsdtar disagree on whether extraction patterns glob by
        # default, so try the portable form first and the GNU flag second.
        tar -xzOf "$target" '*/domains' > "$unpacked" 2>/dev/null || true
        if [ ! -s "$unpacked" ]; then
            tar -xzOf "$target" --wildcards '*/domains' > "$unpacked" 2>/dev/null || true
        fi

        if [ ! -s "$unpacked" ]; then
            echo "Source $index: no domains file inside the archive, excluding: $url ❌" | tee -a "$LOGFILE"
            rm -f "$target" "$unpacked"
            printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$url" "$status" "0" "$elapsed" > "$meta"
            return 1
        fi

        mv "$unpacked" "$target"
        # Report the size of what the pipeline actually reads, not of the archive.
        bytes=$(wc -c < "$target" | tr -d ' ')
        printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$url" "$status" "$bytes" "$elapsed" > "$meta"
        echo "Downloaded source $index (HTTP $status, archive unpacked to ${bytes} bytes): $url" | tee -a "$LOGFILE"
        return 0
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

    # Name the sources that failed. A count alone tells nobody which feed to go
    # and look at, and this log is the first thing read when a release is wrong.
    if [ "$downloaded" -lt "$index" ]; then
        echo "Sources that did not download:" | tee -a "$LOGFILE"
        for meta in "$SOURCES_DIR"/*.meta; do
            [ -f "$meta" ] || continue
            local m_index m_url m_status
            IFS=$'\t' read -r m_index m_url m_status _ _ < "$meta"
            if [ ! -f "${SOURCES_DIR}/$(printf '%03d' "$m_index").fqdn.list" ]; then
                echo "  HTTP ${m_status}: ${m_url}" | tee -a "$LOGFILE"
            fi
        done
    fi

    # A coarse early exit, and deliberately not the real guard.
    #
    # This threshold counts SOURCES, and the project has already been burned by
    # exactly that: on 2026-07-31 two of forty-six sources 404'd and took 46% of
    # the domains with them, because one of them was almost half the list on its
    # own. Forty-four of forty-six downloaded, so a source count saw nothing
    # wrong. Sources are not interchangeable and counting them cannot detect
    # that.
    #
    # What actually protects the release is scripts/check_quality.py, which
    # compares the SIZE of the result against the previously published list in
    # both directions. This check only stops the run early when the fetch was so
    # broken that there is no point continuing.
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
        echo "# Aggregated by fabriziosalmi/blacklists from multiple third-party sources."
        echo "# Generated: ${gen_date} UTC"
        echo "# Domains: ${domain_count}"
        echo "#"
        # The licence has to be stated on the artifact itself. A file that only
        # says "see SOURCES.md" tells someone holding a downloaded copy nothing
        # about what they may do with it, and the released assets are what
        # actually circulate.
        echo "# License: GPL-3.0-only. This is a combined work: the sources are merged"
        echo "#   and deduplicated into one file, so their licenses govern the whole."
        echo "#   Why, and how each source reaches it: LICENSING.md"
        echo "# Attribution: NOTICES.txt, published with every release"
        echo "# Per-source licence map: https://github.com/fabriziosalmi/blacklists/blob/main/SOURCES.md"
        echo "# Source lists: https://github.com/fabriziosalmi/blacklists/blob/main/blacklists.fqdn.urls"
        cat "$target"
    } > "$tmp" && mv "$tmp" "$target"

    echo "Prepended attribution header (${domain_count} domains)." | tee -a "$LOGFILE"
}

# Main routine
main() {
    detect_package_manager
    update_and_install
    check_required_tools
    manage_downloads
    sanitize_and_whitelist
    prepend_attribution_header
    local total_lines_new=$(grep -Evc '^[[:space:]]*#' all.fqdn.blacklist 2>/dev/null || echo 0)
    echo "Total domains: $total_lines_new 🌍." | tee -a "$LOGFILE"
}

main