# Introduction

This project aggregates domain blacklists from multiple upstream sources and publishes a deduplicated, daily-updated list in multiple formats suitable for use with DNS servers, proxies, firewalls, and browser extensions.

## How It Works

1. Source URLs are configured in `blacklists.fqdn.urls` (one URL per line).
2. A GitHub Actions workflow (`release.yml`) runs daily at midnight UTC. It downloads all sources, aggregates and deduplicates the domains, applies the whitelist (`whitelist.txt`), and publishes the result as a GitHub Release.
3. A second workflow (`daily-stats.yml`) runs at 01:00 UTC to update statistics in `README.md` and generate trend charts in `stats/`.

## Output Formats

| File | Format | Use Case |
|------|--------|----------|
| `blacklist.txt` | One domain per line | Pi-Hole, AdGuard Home, uBlock Origin, Squid |
| `unbound_blacklist.txt` | Unbound `local-zone` directives | Unbound DNS |
| `rpz_blacklist.txt` | DNS RPZ zone file | BIND9, PowerDNS |

All formats are published to the `latest` GitHub Release and updated daily.

## Whitelist

Domains listed in `whitelist.txt` are excluded from all output files during generation. To request a domain be whitelisted, [open an issue](https://github.com/fabriziosalmi/blacklists/issues/new/choose).

## Local Mirror

A Docker image (`fabriziosalmi/blacklists`) serves the blacklist files via HTTP and can be used as a local mirror. See the [docker/](../docker/) directory for configuration.

## Further Reading

- [docs/README.md](README.md) — Download URLs and platform setup guides
- [docs/USER_GUIDE.md](USER_GUIDE.md) — Detailed installation instructions per platform
- [docs/MAINTENANCE.md](MAINTENANCE.md) — Managing sources and whitelist
- [docs/DEVOPS.md](DEVOPS.md) — Automation and workflow reference
