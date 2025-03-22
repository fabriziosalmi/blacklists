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

# Function to download a URL and save to a randomly named file
download_url() {
    local url="$1"
    local random_filename=$(uuidgen | tr -dc '[:alnum:]')
    echo "Downloading blacklist: $url -> $random_filename.fqdn.list" | tee -a "$LOGFILE"

    # Use wget or curl based on availability
    if command -v wget &>/dev/null; then
      DOWNLOAD_CMD="wget -q --progress=bar:force -O"
    elif command -v curl &>/dev/null; then
      DOWNLOAD_CMD="curl -s -o" # -s for silent operation, -o for output
    else
      echo "wget or curl not found. Exiting ❌." | tee -a "$LOGFILE"
      exit 1
    fi


    if ! $DOWNLOAD_CMD "$random_filename.fqdn.list" "$url"; then
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
    local aggregated_file="aggregated.fqdn.list" # Store file in variable
    echo "" > "$aggregated_file" # Use variable

    # Debugging: List files before globbing
    echo "Files in current directory:" | tee -a "$LOGFILE"
    ls -l | tee -a "$LOGFILE"

    # Improved globbing and file existence check
    # Exclude aggregated_file
    local files=$(find . -maxdepth 1 -name "*.fqdn.list" ! -name "$aggregated_file" -print0 | xargs -0 ls -l) # List files matching pattern to LOG
    echo "Files matching *.fqdn.list (excluding $aggregated_file):" | tee -a "$LOGFILE"
    echo "$files" | tee -a "$LOGFILE"

    #Check if any matches were found
    if [[ -z "$files" ]]; then
        echo "No *.fqdn.list files found (excluding $aggregated_file). Check your download URLs and file permissions.  Exiting ❌." | tee -a "$LOGFILE"
        exit 1
    fi

    for file in *.fqdn.list; do
      if [ -f "$file" ] && [ "$file" != "$aggregated_file" ]; then
        echo "Processing file: $file" | tee -a "$LOGFILE"
        cat "$file" >> "$aggregated_file"
      else
        if [ "$file" == "$aggregated_file" ]; then
          echo "Skipping $aggregated_file" | tee -a "$LOGFILE"
        else
          echo "File not found: $file. Skipping." | tee -a "$LOGFILE"
        fi
      fi
    done

    sort -u "$aggregated_file" > all.fqdn.blacklist # Use variable

    # Check for an empty blacklist file after sort
    if [ ! -s "all.fqdn.blacklist" ]; then
      echo "all.fqdn.blacklist is empty after sort. Check input data and sort command. Exiting ❌" | tee -a "$LOGFILE"
      exit 1
    fi

    echo "Cleanup: removing source files..." | tee -a "$LOGFILE"
    rm -f ./*.fqdn.list "$aggregated_file"
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