import json
import requests

# Constants
API_ENDPOINT = "https://api-ipres.domainsblacklists.com/resolve"
TIMEOUT = 3
MAX_IPS = 10  # Change this as per your requirement
INPUT_FILE = "blacklist.ip.txt"
OUTPUT_FILE = "blacklist.ip.resolved.txt"

# Fetch the blacklisted IPs
try:
    with open(INPUT_FILE, "r") as file:
        IPS = [line.strip() for line in file if line.strip()][:MAX_IPS]  # Ignore empty lines
except FileNotFoundError:
    print(f"Error: File '{INPUT_FILE}' not found.")
    exit(1)

RESOLVED_IPS = []

for ip in IPS:
    try:
        response = requests.get(f"{API_ENDPOINT}/{ip}", timeout=TIMEOUT)

        if response.status_code != 200:
            continue

        data = response.json()
        resolved_name = data.get("fqdn", "").strip()

        # Skip NXDOMAIN and non-resolvable IPs
        if not resolved_name or "nxdomain" in resolved_name.lower():
            continue

        # Remove trailing dot if present
        RESOLVED_IPS.append(resolved_name.rstrip('.'))

    except (requests.RequestException, json.JSONDecodeError):
        continue  # Silently ignore errors

# Save to output file
if RESOLVED_IPS:
    with open(OUTPUT_FILE, "w") as out_file:
        out_file.write("\n".join(RESOLVED_IPS) + "\n")
else:
    print("No resolvable IPs found.")
