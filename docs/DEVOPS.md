# DevOps Guide

This guide covers the automation and operational aspects of the Blacklists project.

---

## Blacklist Automation

### Daily Generation Workflow

The blacklist is automatically generated daily at midnight UTC using GitHub Actions.

**Workflow Schedule:**
- **00:00 UTC**: Generate and publish blacklist (`release.yml`)
- **01:00 UTC**: Update statistics and README (`daily-stats.yml`)

**Workflow Files:**
- `.github/workflows/release.yml` — Main blacklist generation
- `.github/workflows/daily-stats.yml` — Statistics and README updates

### Manual Triggering

To trigger workflows manually:

```bash
# Using GitHub CLI
gh workflow run release.yml
gh workflow run daily-stats.yml

# Or via GitHub web interface:
# Actions → Select workflow → Run workflow
```

### Monitoring Workflows

Check workflow status:

```bash
# List recent runs
gh run list --workflow=release.yml --limit 10

# View specific run
gh run view <run-id>

# Watch live
gh run watch
```

---

## Security Best Practices

### HTTPS

Always use HTTPS when serving the blacklist files to downstream clients.

### Security Headers

When self-hosting a mirror, ensure these headers are set:

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Deployment Checklist

Before deploying changes:

- [ ] Verify blacklist source URLs are reachable
- [ ] Test whitelist entries are correctly excluded
- [ ] Confirm workflow files are syntactically valid
- [ ] Check that output formats are correctly generated
- [ ] Review statistics scripts for correctness

---

## Troubleshooting

### Workflow Failures

If the daily workflow fails:

1. Check [Actions](https://github.com/fabriziosalmi/blacklists/actions) for error logs
2. Common issues:
   - Source URL timeout: Remove or replace the problematic source in `blacklists.fqdn.urls`
   - Disk space: Workflow should clean up automatically
   - Rate limiting: Wait for the next scheduled run or trigger manually

### Statistics Not Updating

If statistics are not updating:

1. Check `daily-stats.yml` workflow status
2. Verify the `stats/` directory exists
3. Ensure Python dependencies are installed
4. Run manually: `python3 scripts/generate_stats.py --test`

---

## Support

- [GitHub Discussions](https://github.com/fabriziosalmi/blacklists/discussions)
- [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)
