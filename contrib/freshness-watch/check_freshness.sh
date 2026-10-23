#!/bin/bash
# Alert when the published blacklist stops being updated.
#
# Runs on a machine of the maintainer's, not in GitHub Actions, so the webhook
# URL never has to be stored in the repository's secrets. It reads only public
# data: the upload time of blacklist.txt on the "latest" release, from the
# unauthenticated GitHub API.
#
# Why this exists: the release failed for 35 nights from 2026-09-18 and the
# only signal was an issue in the repository itself. A failing workflow cannot
# be trusted to report its own failure, so this watches the result instead.
#
# Configuration, all optional except the webhook file:
#   BLACKLISTS_WEBHOOK_FILE  file holding the webhook URL, one line, mode 600
#                            (default ~/.config/blacklists-freshness/webhook_url)
#   BLACKLISTS_STATE_DIR     where the alert state lives
#                            (default ~/.local/state/blacklists-freshness)
#   BLACKLISTS_STALE_HOURS   age beyond which the list is stale (default 36)
#   BLACKLISTS_API_URL       release endpoint (default the public GitHub API)
#
# Alerts at most once every 24 hours while the list is stale, once when it
# recovers, and once a day if the check itself cannot reach GitHub for more
# than 24 hours, so a broken watcher is not mistaken for a healthy list.
#
# Exit status: 0 fresh, 1 stale, 2 the check could not run.

set -euo pipefail

WEBHOOK_FILE="${BLACKLISTS_WEBHOOK_FILE:-$HOME/.config/blacklists-freshness/webhook_url}"
STATE_DIR="${BLACKLISTS_STATE_DIR:-$HOME/.local/state/blacklists-freshness}"
STALE_HOURS="${BLACKLISTS_STALE_HOURS:-36}"
API_URL="${BLACKLISTS_API_URL:-https://api.github.com/repos/fabriziosalmi/blacklists/releases/tags/latest}"
REALERT_SECONDS=86400

mkdir -p "$STATE_DIR"
now=$(date -u +%s)

log() { echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*"; }

read_state() { cat "$STATE_DIR/$1" 2>/dev/null || echo 0; }

# The URL is read here and nowhere else, and never printed: curl gets it from
# a config on stdin so it does not appear in the process list either.
send() {
  local message=$1
  if [ ! -r "$WEBHOOK_FILE" ]; then
    log "cannot alert: webhook file $WEBHOOK_FILE is missing or unreadable"
    return 1
  fi
  local url
  url=$(head -n 1 "$WEBHOOK_FILE" | tr -d '[:space:]')
  # "text" is read by Slack, Mattermost and most generic receivers, "content"
  # by Discord; each ignores the other.
  local payload
  payload=$(jq -cn --arg m "$message" '{text: $m, content: $m}')
  if printf 'url = "%s"\n' "$url" | curl -fsS --max-time 20 -K - \
      -H 'Content-Type: application/json' --data "$payload" -o /dev/null; then
    log "alert sent: $message"
  else
    log "alert FAILED to send: $message"
    return 1
  fi
}

for tool in curl jq; do
  command -v "$tool" >/dev/null || { log "missing dependency: $tool"; exit 2; }
done

if ! response=$(curl -fsS --max-time 30 -H 'Accept: application/vnd.github+json' "$API_URL"); then
  last_ok=$(read_state last_ok)
  log "could not reach $API_URL"
  if [ "$last_ok" -gt 0 ] && [ $((now - last_ok)) -gt "$REALERT_SECONDS" ] \
      && [ $((now - $(read_state last_unreachable_alert))) -ge "$REALERT_SECONDS" ]; then
    send "blacklists freshness check has not reached GitHub for $(( (now - last_ok) / 3600 )) hours; the list age is unknown." \
      && echo "$now" > "$STATE_DIR/last_unreachable_alert"
  fi
  exit 2
fi

updated=$(jq -r '.assets[] | select(.name == "blacklist.txt") | .updated_at' <<<"$response")
if [ -z "$updated" ] || [ "$updated" = "null" ]; then
  log "no blacklist.txt asset on the latest release"
  if [ $((now - $(read_state last_stale_alert))) -ge "$REALERT_SECONDS" ]; then
    send "blacklists: the latest release has no blacklist.txt asset." \
      && echo "$now" > "$STATE_DIR/last_stale_alert"
  fi
  exit 1
fi

echo "$now" > "$STATE_DIR/last_ok"
published=$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$updated" +%s)
age_hours=$(( (now - published) / 3600 ))

if [ "$age_hours" -le "$STALE_HOURS" ]; then
  log "fresh: blacklist.txt uploaded $updated, ${age_hours}h ago"
  if [ "$(read_state stale)" = "1" ]; then
    send "blacklists recovered: blacklist.txt uploaded $updated, ${age_hours}h ago." || true
    echo 0 > "$STATE_DIR/stale"
    echo 0 > "$STATE_DIR/last_stale_alert"
  fi
  exit 0
fi

log "STALE: blacklist.txt uploaded $updated, ${age_hours}h ago (limit ${STALE_HOURS}h)"
echo 1 > "$STATE_DIR/stale"
if [ $((now - $(read_state last_stale_alert))) -ge "$REALERT_SECONDS" ]; then
  send "blacklists is stale: blacklist.txt was last uploaded $updated, ${age_hours} hours ago. https://github.com/fabriziosalmi/blacklists/actions/workflows/release.yml" \
    && echo "$now" > "$STATE_DIR/last_stale_alert"
fi
exit 1
