# Freshness watch

Alerts a webhook when the published `blacklist.txt` has not been updated for
more than 36 hours. It runs on a machine you control, under launchd, so the
webhook URL stays on that machine and is never stored in GitHub.

It reads only public data, the upload time of `blacklist.txt` on the `latest`
release, from the unauthenticated GitHub API. Every 6 hours is 4 requests a
day, far below the anonymous limit of 60 an hour.

## What it sends

| Situation | Message |
|---|---|
| `blacklist.txt` older than 36 hours | one alert, repeated every 24 hours while it lasts |
| The list is fresh again | one recovery message |
| GitHub unreachable for more than 24 hours | one alert a day, so a broken watcher is not mistaken for a healthy list |
| The release has no `blacklist.txt` | one alert, repeated every 24 hours |

The JSON body carries the message as both `text` (Slack, Mattermost and most
generic receivers) and `content` (Discord).

## Install (macOS)

```bash
# 1. The webhook URL, readable only by you. Paste it on stdin so it does not
#    land in your shell history.
mkdir -p ~/.config/blacklists-freshness
( umask 077; cat > ~/.config/blacklists-freshness/webhook_url )

# 2. The launchd job, with the placeholders filled in.
REPO="$PWD"   # run from the repository root
sed -e "s|__SCRIPT__|$REPO/contrib/freshness-watch/check_freshness.sh|" \
    -e "s|__HOME__|$HOME|" \
    contrib/freshness-watch/io.github.fabriziosalmi.blacklists-freshness.plist \
    > ~/Library/LaunchAgents/io.github.fabriziosalmi.blacklists-freshness.plist
launchctl bootstrap "gui/$(id -u)" \
    ~/Library/LaunchAgents/io.github.fabriziosalmi.blacklists-freshness.plist

# 3. It runs once at load. Check it.
tail -n 5 ~/Library/Logs/blacklists-freshness.log
```

Requires `curl` and `jq` (`brew install jq`).

To test the alert path without waiting for a stale list, set a limit the list
always exceeds and use a throwaway state directory:

```bash
BLACKLISTS_STALE_HOURS=-1 BLACKLISTS_STATE_DIR=$(mktemp -d) \
    contrib/freshness-watch/check_freshness.sh
```

To remove it:

```bash
launchctl bootout "gui/$(id -u)/io.github.fabriziosalmi.blacklists-freshness"
rm ~/Library/LaunchAgents/io.github.fabriziosalmi.blacklists-freshness.plist
```
