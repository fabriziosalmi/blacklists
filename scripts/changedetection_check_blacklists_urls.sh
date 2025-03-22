#!/bin/bash

# requirements: curl, jq

CHANGEDETECTION_HOST=localhost
CHANGEDETECTION_PORT=5000
CHANGEDETECTION_KEY=01234567891011121314116
curl http://$CHANGEDETECTION_HOST:$CHANGEDETECTION_PORT/api/v1/watch -H "x-api-key: $CHANGEDETECTION_KEY" | jq . > data.json

# Parse JSON data using jq and filter URLs where last_changed is not equal to 0
filtered_urls=$(jq '.[] | select(.last_changed != 0) | .url' data.json)

# Write the filtered URLs to a new text file
echo "$filtered_urls" > blacklists.urls

rm data.json
echo "Filtered URLs have been written to 'blacklists.urls' file."
