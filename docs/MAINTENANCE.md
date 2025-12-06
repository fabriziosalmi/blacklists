# Maintenance Guide

This guide provides information on maintaining the blacklists project.

## Daily Automated Updates

The blacklist is automatically updated **daily at midnight UTC** via GitHub Actions. This schedule balances freshness with cost-effectiveness, keeping the service free for everyone.

### Why Daily Instead of Hourly?

- **Cost Efficiency**: Daily updates significantly reduce GitHub Actions usage costs
- **Sufficient Freshness**: Most threats don't require hourly updates
- **Sustainability**: Keeps the service free and accessible to all users
- **Resource Optimization**: Reduces unnecessary processing and bandwidth

## Updating Blacklist Sources

### Adding a New Source

1. Edit `blacklists.fqdn.urls`
2. Add the URL of the new blacklist (one per line)
3. Commit and push the changes
4. The next daily run will include the new source

### Removing a Source

1. Edit `blacklists.fqdn.urls`
2. Remove or comment out (with `#`) the URL
3. Commit and push the changes

### Testing a Source

Before adding a new source permanently, test it:

```bash
# Download and inspect the source
wget -O test_source.txt "https://example.com/blacklist.txt"
head -n 100 test_source.txt

# Check format and quality
wc -l test_source.txt
grep -E '^[a-z0-9.-]+\.[a-z]{2,}$' test_source.txt | wc -l
```

## Whitelist Management

### Adding Domains to Whitelist

1. Edit `whitelist.txt`
2. Add domains (one per line)
3. Commit and push
4. Domains will be excluded in the next daily run

### Bulk Whitelist Updates

For large whitelist updates, users can submit via:
- GitHub Issues: [Submit whitelist request](https://github.com/fabriziosalmi/blacklists/issues/new/choose)
- Pull Requests: Direct PR to `whitelist.txt`

## Review Process

### Regular Blacklist Reviews

Conduct periodic reviews of source blacklists:

1. Check `docs/blacklists_reviews.md` for review schedule
2. Test random samples from each source
3. Verify sources are still active and maintained
4. Remove inactive or low-quality sources

### Quality Metrics

Monitor these metrics:

- Total domains count (should grow steadily)
- Whitelist size (should remain manageable)
- Number of active sources
- False positive reports

## Release Workflow

### Automated Release Process

The daily workflow automatically:

1. **00:00 UTC**: Generates blacklist
   - Downloads all sources
   - Aggregates and deduplicates
   - Applies whitelist
   - Creates release with multiple formats

2. **01:00 UTC**: Updates statistics
   - Analyzes growth trends
   - Updates README badges
   - Generates trend charts
   - Commits statistics

### Manual Release Trigger

To trigger a manual update:

1. Go to [Actions](https://github.com/fabriziosalmi/blacklists/actions)
2. Select "Generate and Publish Blacklists" workflow
3. Click "Run workflow"
4. Select branch (usually `main`)
5. Click "Run workflow"

## Monitoring

### Check Workflow Status

Monitor workflow health:

```bash
# View recent workflow runs
gh run list --workflow=release.yml --limit 10

# Check specific run
gh run view <run-id>
```

### Statistics Dashboard

Daily statistics are automatically updated in:
- `README.md` (main statistics section)
- `stats/daily_stats.json` (raw data)
- `stats/history.csv` (historical data)
- `stats/trend.png` (visual chart)

## Troubleshooting

### Workflow Failures

If the daily workflow fails:

1. Check [Actions](https://github.com/fabriziosalmi/blacklists/actions) for error logs
2. Common issues:
   - Source URL timeout: Remove or replace problematic source
   - Disk space: Workflow should clean up automatically
   - Rate limiting: Wait for next scheduled run

### Statistics Not Updating

If statistics aren't updating:

1. Check `daily-stats.yml` workflow status
2. Verify `stats/` directory exists
3. Ensure Python dependencies are installed
4. Run manually: `python3 scripts/generate_stats.py --test`

## Backup and Recovery

### Backup Important Files

Key files to backup:

- `blacklists.fqdn.urls` - Source list
- `whitelist.txt` - Whitelist
- `stats/history.csv` - Historical data

### Recovery

If data is lost, historical blacklists can be recovered from:

- GitHub Releases (tagged as `latest`)
- Git history
- Docker Hub mirror

## Contributing to Maintenance

Contributors can help by:

- Reporting dead sources
- Suggesting new quality sources
- Submitting whitelist improvements
- Improving documentation
- Testing and reporting issues

For more information, see [CONTRIBUTING.md](../CONTRIBUTING.md).
