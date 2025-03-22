"""
This script checks the last modification dates for URLs and creates a markdown report.
It is particularly tailored for checking blacklist URLs.
"""

import os
from datetime import datetime
from time import sleep

import requests
from tqdm import tqdm

# File paths and directories
BLACKLISTS_URL_FILE = 'blacklists.fqdn.urls'
BLACKLIST_MONITOR_DIR = 'blacklist-monitor'
GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/commits?path={path}"

def get_last_modified(url):
    try:
        if 'raw.githubusercontent.com' in url:
            # Parsing the URL to retrieve repository details
            parts = url.split("/")
            owner = parts[3]
            repo = parts[4]
            path = "/".join(parts[5:])
            api_url = GITHUB_API_URL.format(owner=owner, repo=repo, path=path)

            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            if data and 'commit' in data[0] and 'committer' in data[0]['commit']:
                return data[0]['commit']['committer']['date']
            else:
                return "N/A"
        else:
            response = requests.head(url, timeout=10)
            if response.status_code == 200 and 'Last-Modified' in response.headers:
                return response.headers['Last-Modified']
            return "N/A"
    except requests.RequestException:
        return "Error"

def main():
    # Create the blacklist-monitor directory if it doesn't exist
    os.makedirs(BLACKLIST_MONITOR_DIR, exist_ok=True)

    while True:
        with open(BLACKLISTS_URL_FILE, 'r') as file_handle:
            urls = [line.strip() for line in file_handle]

        table_data = []

        print("Checking blacklist URLs...")
        for url in urls:
            last_modified = get_last_modified(url)
            table_data.append((url, last_modified))

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        monitor_file = os.path.join(BLACKLIST_MONITOR_DIR, f"blacklists_monitor_{timestamp}.md")

        # Update the markdown file
        with open(monitor_file, 'w') as file_handle:
            file_handle.write("# Blacklists Monitor\n\n")
            file_handle.write("| URL | Last Modified |\n")
            file_handle.write("| --- | ------------- |\n")
            for data in table_data:
                file_handle.write(f"| {data[0]} | {data[1]} |\n")

        print(f"Updated {monitor_file}!")

if __name__ == '__main__':
    main()
