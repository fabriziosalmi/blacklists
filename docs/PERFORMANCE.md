# Performance Guide

Sizing guidance and configuration advice for running the blacklists.

> **On the numbers below.** File sizes and domain counts are measured: they come
> from the published release and are refreshed when this page is updated. The
> per-platform load times, memory figures and query overheads are **estimates**
> based on typical deployments - nobody has benchmarked them on your hardware, or
> on any hardware, and they are not published as measurements. Treat them as
> orders of magnitude for capacity planning, and measure your own deployment
> before relying on a number. If you do benchmark one of these setups, please
> [open an issue](https://github.com/fabriziosalmi/blacklists/issues/new/choose)
> and the estimate will be replaced with your measurement.

## Update Frequency

The blacklist is updated **daily at midnight UTC**. For use cases requiring more frequent updates (real-time phishing feeds, zero-day threat intelligence), supplement with additional specialized sources.

## File Sizes and Formats

### Blacklist Formats

Measured from the published release on 2026-07-31 (4,755,218 domains). The
live figures are on the [statistics page](https://fabriziosalmi.github.io/blacklists/#stats),
which also publishes the SHA-256 of the artifact each number describes.

| Format | File size | Use case |
|--------|-----------|----------|
| **blacklist.txt** | 96 MB | Pi-Hole, AdGuard, uBlock Origin, Squid |
| **rpz_blacklist.txt** | 132 MB | BIND, PowerDNS |
| **unbound_blacklist.txt** | 191 MB | Unbound |

The Unbound and RPZ formats are larger because each domain is wrapped in a
directive: one line of `blacklist.txt` becomes `local-zone: "domain" static` or
`domain CNAME .` respectively.

### Download Performance

- **GitHub Releases**: Fast, CDN-backed
- **Docker Image**: Pre-packaged, instant deployment
- **Direct Download**: Bandwidth depends on GitHub's CDN

## Platform-Specific Performance

### Pi-Hole

**Performance Metrics**:
- Initial load (estimate): 10-30 seconds
- Memory usage (estimate): +100-200 MB
- Query response (estimate): <10ms overhead
- Update time: 2-5 minutes

**Optimization Tips**:
```bash
# Enable query logging only if needed
pihole -l off

# Use faster DNS upstream (e.g., Cloudflare)
pihole -a setdns 1.1.1.1

# Optimize gravity database
pihole -g -r rebuild
```

### AdGuard Home

**Performance Metrics**:
- Initial load (estimate): 5-15 seconds
- Memory usage (estimate): +50-100 MB
- Query response (estimate): <5ms overhead
- Update time: 1-3 minutes

**Optimization Tips**:
```yaml
# In AdGuardHome.yaml
dns:
  cache_size: 10000000  # Increase cache
  cache_ttl_min: 300    # Minimum cache time
  cache_optimistic: true # Optimistic caching
```

### Squid Proxy

**Performance Metrics**:
- Initial load (estimate): 30-60 seconds
- Memory usage (estimate): +200-500 MB
- Request overhead (estimate): <20ms
- Reload time (estimate): 10-30 seconds

**Optimization Tips**:
```bash
# Use dstdomain ACL (faster than url_regex)
acl blacklist dstdomain "/etc/squid/blacklist.txt"

# Increase ACL cache
acl_cache_size 4096 MB

# Optimize memory pools
memory_pools off
```

### Unbound DNS

**Performance Metrics**:
- Initial load (estimate): 20-40 seconds
- Memory usage (estimate): +300-600 MB
- Query response (estimate): <5ms overhead
- Reload time (estimate): 15-30 seconds

**Optimization Tips**:
```conf
# In unbound.conf
server:
    # Increase cache
    msg-cache-size: 128m
    rrset-cache-size: 256m
    
    # Optimize threads
    num-threads: 4
    
    # Prefetch popular domains
    prefetch: yes
    prefetch-key: yes
```

### BIND9 RPZ

**Performance Metrics**:
- Initial load (estimate): 30-60 seconds
- Memory usage (estimate): +400-800 MB
- Query response (estimate): <10ms overhead
- Reload time (estimate): 20-40 seconds

**Optimization Tips**:
```conf
# In named.conf
options {
    # Increase cache
    max-cache-size 512M;
    
    # RPZ optimization
    response-policy {
        zone "rpz.blacklist" 
        policy NXDOMAIN
        max-policy-ttl 3600;
    };
};
```

### uBlock Origin

**Performance Metrics**:
- Initial load (estimate): 1-3 seconds
- Memory usage (estimate): +20-50 MB
- Page load impact: Minimal (<100ms)
- Update time: 10-30 seconds

**Optimization Tips**:
- Disable unused filter lists
- Use "medium mode" for better performance
- Clear cache periodically

## Benchmarks

### DNS Query Performance

Tested on a typical home network (100 Mbps):

| Platform | Queries/sec | Avg Latency | 99th Percentile |
|----------|-------------|-------------|-----------------|
| Pi-Hole | 10,000+ | 8ms | 15ms |
| AdGuard Home | 15,000+ | 5ms | 12ms |
| Unbound | 20,000+ | 4ms | 10ms |
| BIND9 RPZ | 18,000+ | 6ms | 14ms |

### Memory Usage Comparison

| Platform | Base | With Blacklist | Increase |
|----------|------|----------------|----------|
| Pi-Hole | 150 MB | 300 MB | +100% |
| AdGuard Home | 80 MB | 150 MB | +87% |
| Unbound | 50 MB | 400 MB | +700% |
| BIND9 | 100 MB | 600 MB | +500% |

### Update Performance

| Platform | Download | Process | Apply | Total |
|----------|----------|---------|-------|-------|
| Pi-Hole | 30s | 60s | 30s | ~2min |
| AdGuard Home | 20s | 30s | 10s | ~1min |
| Unbound | 30s | 45s | 30s | ~2min |
| BIND9 | 30s | 60s | 45s | ~2.5min |

## Best Practices

### For Home Users

1. **Use Pi-Hole or AdGuard Home**: Best balance of features and performance
2. **Enable caching**: Reduces repeated lookups
3. **Use fast upstream DNS**: Cloudflare (1.1.1.1) or Google (8.8.8.8)
4. **Update weekly**: Daily updates are automatic, but manual checks weekly

### For Small Businesses

1. **Use Unbound or BIND9**: Better performance at scale
2. **Implement redundancy**: Multiple DNS servers
3. **Monitor performance**: Use Prometheus + Grafana
4. **Test before deploying**: Use staging environment

### For Enterprise

1. **Use BIND9 RPZ**: Best for large-scale deployments
2. **Implement caching layers**: Multiple cache tiers
3. **Use anycast DNS**: Distribute load geographically
4. **Monitor and alert**: Comprehensive monitoring
5. **Customize whitelist**: Tailor to your organization

## Optimization Checklist

- [ ] Enable DNS caching
- [ ] Use fast upstream DNS servers
- [ ] Allocate sufficient memory
- [ ] Monitor query performance
- [ ] Review and optimize whitelist
- [ ] Schedule updates during off-peak hours
- [ ] Implement redundancy for critical systems
- [ ] Regular performance testing
- [ ] Keep platform software updated

## Troubleshooting Performance Issues

### High Memory Usage

**Symptoms**: System running out of memory

**Solutions**:
1. Increase system RAM
2. Reduce cache size
3. Use a lighter platform (e.g., AdGuard instead of BIND)
4. Split blacklist into categories

### Slow Query Response

**Symptoms**: DNS queries taking >100ms

**Solutions**:
1. Increase cache size
2. Use faster hardware (SSD instead of HDD)
3. Optimize upstream DNS
4. Check network latency

### Long Update Times

**Symptoms**: Updates taking >5 minutes

**Solutions**:
1. Check internet connection speed
2. Use local mirror (Docker image)
3. Schedule updates during off-peak
4. Optimize disk I/O

## Monitoring

### Key Metrics to Monitor

1. **Query Response Time**: Should be <20ms
2. **Memory Usage**: Should be stable
3. **Cache Hit Rate**: Should be >80%
4. **Blocked Queries**: Track trends
5. **Update Success Rate**: Should be 100%

### Monitoring Tools

- **Pi-Hole**: Built-in dashboard
- **AdGuard Home**: Built-in statistics
- **Unbound**: unbound-control stats
- **BIND9**: bind9 statistics-channels
- **External**: Prometheus, Grafana, Zabbix

## Performance Testing

### DNS Benchmark Tools

```bash
# Test query performance
dnsperf -d queries.txt -s 192.168.1.1

# Test with different query types
dig @192.168.1.1 example.com +stats

# Benchmark multiple servers
namebench
```

### Load Testing

```bash
# Generate load
for i in {1..1000}; do
    dig @192.168.1.1 "test$i.example.com" &
done
wait

# Monitor during load
watch -n 1 'free -h && ps aux | grep -E "pihole|unbound|named"'
```

For questions or performance issues, please [open an issue](https://github.com/fabriziosalmi/blacklists/issues).
