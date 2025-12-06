# Troubleshooting Guide

This guide helps you resolve common issues with the blacklists.

## Table of Contents

- [General Issues](#general-issues)
- [Pi-Hole](#pi-hole)
- [AdGuard Home](#adguard-home)
- [Squid Proxy](#squid-proxy)
- [Unbound DNS](#unbound-dns)
- [BIND9 RPZ](#bind9-rpz)
- [uBlock Origin](#ublock-origin)
- [Performance Issues](#performance-issues)
- [False Positives](#false-positives)

## General Issues

### Blacklist Not Downloading

**Symptoms**: Cannot download blacklist from GitHub

**Solutions**:

1. **Check GitHub status**: Visit [GitHub Status](https://www.githubstatus.com/)

2. **Try alternative URL**:
```bash
# Instead of releases URL, try raw file
wget https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/all.fqdn.blacklist
```

3. **Check network connectivity**:
```bash
ping github.com
curl -I https://github.com
```

4. **Use Docker mirror**:
```bash
docker pull fabriziosalmi/blacklists:latest
docker run -p 80:80 fabriziosalmi/blacklists
# Access at http://localhost/blacklist.txt
```

### Blacklist File Corrupted

**Symptoms**: File appears corrupted or incomplete

**Solutions**:

1. **Verify file integrity**:
```bash
# Check file size (should be 50-100 MB)
ls -lh blacklist.txt

# Check line count (should be 2-3 million)
wc -l blacklist.txt

# Check for binary data
file blacklist.txt  # Should say "ASCII text"
```

2. **Re-download**:
```bash
rm blacklist.txt
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```

3. **Verify format**:
```bash
# Should show domain names
head -n 10 blacklist.txt

# Check for invalid lines
grep -v -E '^[a-z0-9.-]+\.[a-z]{2,}$' blacklist.txt | head
```

## Pi-Hole

### Blacklist Not Loading

**Symptoms**: Gravity update fails or blacklist not applied

**Solutions**:

1. **Check adlist URL**:
```bash
# Verify URL in Pi-Hole
sqlite3 /etc/pihole/gravity.db "SELECT * FROM adlist;"
```

2. **Manual gravity update**:
```bash
pihole -g -r rebuild
```

3. **Check disk space**:
```bash
df -h /
# Need at least 1 GB free
```

4. **Check logs**:
```bash
tail -f /var/log/pihole/pihole.log
tail -f /var/log/pihole/FTL.log
```

5. **Verify FTL is running**:
```bash
sudo systemctl status pihole-FTL
sudo systemctl restart pihole-FTL
```

### Domains Not Being Blocked

**Symptoms**: Known bad domains are not blocked

**Solutions**:

1. **Verify domain is in blacklist**:
```bash
pihole -q doubleclick.net
```

2. **Check if domain is whitelisted**:
```bash
pihole -w -l | grep doubleclick
```

3. **Flush DNS cache**:
```bash
pihole restartdns
```

4. **Check client DNS settings**:
```bash
# On client machine
nslookup google.com
# Should show Pi-Hole IP as server
```

5. **Test directly**:
```bash
dig @192.168.1.1 doubleclick.net
# Replace with your Pi-Hole IP
```

### High Memory Usage

**Symptoms**: Pi-Hole using too much RAM

**Solutions**:

1. **Check gravity database size**:
```bash
ls -lh /etc/pihole/gravity.db
```

2. **Optimize database**:
```bash
pihole -g -r rebuild
sqlite3 /etc/pihole/gravity.db "VACUUM;"
```

3. **Reduce cache size** (in `/etc/dnsmasq.d/01-pihole.conf`):
```conf
cache-size=10000
```

4. **Restart FTL**:
```bash
sudo systemctl restart pihole-FTL
```

## AdGuard Home

### Filter Not Updating

**Symptoms**: Blacklist shows old data

**Solutions**:

1. **Force update**:
   - Go to Filters → DNS blocklists
   - Click "Update filters"

2. **Check filter URL**:
   - Verify URL is correct
   - Test URL in browser

3. **Check logs**:
```bash
# AdGuard Home logs location varies
journalctl -u AdGuardHome -f
# Or check web UI → Settings → Query Log
```

4. **Restart AdGuard**:
```bash
sudo systemctl restart AdGuardHome
```

### Domains Not Being Blocked

**Symptoms**: Ads still showing

**Solutions**:

1. **Check if filter is enabled**:
   - Go to Filters → DNS blocklists
   - Ensure blacklist is checked

2. **Verify DNS settings on client**:
```bash
# Should point to AdGuard Home
cat /etc/resolv.conf
```

3. **Check query log**:
   - Go to Query Log
   - Search for domain
   - Check if it's being blocked

4. **Clear DNS cache**:
```bash
# On client
sudo systemd-resolve --flush-caches  # Linux
sudo dscacheutil -flushcache  # macOS
ipconfig /flushdns  # Windows
```

### Performance Issues

**Symptoms**: Slow DNS queries

**Solutions**:

1. **Increase cache size** (in `AdGuardHome.yaml`):
```yaml
dns:
  cache_size: 10000000
```

2. **Use faster upstream DNS**:
```yaml
dns:
  bootstrap_dns:
    - 1.1.1.1
    - 1.0.0.1
  upstream_dns:
    - https://dns.cloudflare.com/dns-query
```

3. **Enable optimistic cache**:
```yaml
dns:
  cache_optimistic: true
```

## Squid Proxy

### ACL Not Working

**Symptoms**: Blocked domains are accessible

**Solutions**:

1. **Check ACL syntax**:
```bash
sudo squid -k parse
```

2. **Verify blacklist path**:
```bash
ls -l /etc/squid/conf.d/blacklist.txt
```

3. **Check ACL order** (in `squid.conf`):
```conf
# Deny should come before allow
http_access deny blacklist
http_access allow localnet
```

4. **Reload Squid**:
```bash
sudo squid -k reconfigure
```

5. **Check logs**:
```bash
tail -f /var/log/squid/access.log
tail -f /var/log/squid/cache.log
```

### High Memory Usage

**Symptoms**: Squid consuming too much RAM

**Solutions**:

1. **Optimize ACL** (use dstdomain instead of url_regex):
```conf
acl blacklist dstdomain "/etc/squid/conf.d/blacklist.txt"
```

2. **Reduce cache size** (in `squid.conf`):
```conf
cache_mem 256 MB
maximum_object_size_in_memory 512 KB
```

3. **Disable memory pools**:
```conf
memory_pools off
```

### Slow Performance

**Symptoms**: Proxy requests are slow

**Solutions**:

1. **Increase ACL cache**:
```conf
acl_cache_size 4096 MB
```

2. **Optimize DNS**:
```conf
dns_nameservers 1.1.1.1 8.8.8.8
```

3. **Check disk I/O**:
```bash
iostat -x 1
```

## Unbound DNS

### Configuration Errors

**Symptoms**: Unbound fails to start

**Solutions**:

1. **Check configuration syntax**:
```bash
sudo unbound-checkconf
```

2. **Verify blacklist file**:
```bash
# Check file exists
ls -l /path/to/unbound_blacklist.txt

# Verify format
head -n 5 /path/to/unbound_blacklist.txt
# Should show: local-zone: "domain.com" static
```

3. **Check file permissions**:
```bash
sudo chown unbound:unbound /path/to/unbound_blacklist.txt
sudo chmod 644 /path/to/unbound_blacklist.txt
```

4. **Check logs**:
```bash
sudo journalctl -u unbound -f
```

### Domains Not Being Blocked

**Symptoms**: Queries returning results for blocked domains

**Solutions**:

1. **Verify zone is loaded**:
```bash
sudo unbound-control list_local_zones | grep doubleclick
```

2. **Reload configuration**:
```bash
sudo unbound-control reload
```

3. **Test query**:
```bash
dig @127.0.0.1 doubleclick.net
# Should return NXDOMAIN or static response
```

4. **Check include directive** (in `unbound.conf`):
```conf
server:
    include: /path/to/unbound_blacklist.txt
```

### High Memory Usage

**Symptoms**: Unbound using excessive RAM

**Solutions**:

1. **Reduce cache size** (in `unbound.conf`):
```conf
server:
    msg-cache-size: 64m
    rrset-cache-size: 128m
```

2. **Limit threads**:
```conf
server:
    num-threads: 2
```

3. **Check memory usage**:
```bash
sudo unbound-control stats_noreset | grep mem
```

## BIND9 RPZ

### RPZ Zone Not Loading

**Symptoms**: BIND fails to load RPZ zone

**Solutions**:

1. **Check zone file syntax**:
```bash
sudo named-checkzone rpz.blacklist /path/to/rpz_blacklist.txt
```

2. **Check configuration**:
```bash
sudo named-checkconf
```

3. **Verify zone file format**:
```bash
head -n 10 /path/to/rpz_blacklist.txt
# Should show: domain.com CNAME .
```

4. **Check file permissions**:
```bash
sudo chown bind:bind /path/to/rpz_blacklist.txt
sudo chmod 644 /path/to/rpz_blacklist.txt
```

5. **Check logs**:
```bash
sudo journalctl -u named -f
tail -f /var/log/syslog | grep named
```

### Domains Not Being Blocked

**Symptoms**: RPZ not blocking domains

**Solutions**:

1. **Verify RPZ is enabled** (in `named.conf`):
```conf
options {
    response-policy {
        zone "rpz.blacklist";
    };
};
```

2. **Check RPZ statistics**:
```bash
sudo rndc stats
cat /var/cache/bind/named.stats | grep RPZ
```

3. **Reload zone**:
```bash
sudo rndc reload rpz.blacklist
```

4. **Test query**:
```bash
dig @localhost doubleclick.net
# Should return NXDOMAIN
```

### Performance Issues

**Symptoms**: Slow query responses

**Solutions**:

1. **Increase cache size** (in `named.conf`):
```conf
options {
    max-cache-size 512M;
};
```

2. **Optimize RPZ** (in `named.conf`):
```conf
options {
    response-policy {
        zone "rpz.blacklist" 
        policy NXDOMAIN
        max-policy-ttl 3600;
    };
};
```

3. **Check query performance**:
```bash
sudo rndc status
```

## uBlock Origin

### Filter Not Updating

**Symptoms**: Blacklist shows old version

**Solutions**:

1. **Force update**:
   - Open uBlock Origin dashboard
   - Go to "Filter lists"
   - Click "Purge all caches"
   - Click "Update now"

2. **Check filter URL**:
   - Verify URL is correct in custom filters
   - Test URL in browser

3. **Clear browser cache**:
   - Ctrl+Shift+Delete
   - Clear cached images and files

### Domains Not Being Blocked

**Symptoms**: Ads still showing

**Solutions**:

1. **Verify filter is enabled**:
   - Check filter list is checked
   - Ensure uBlock Origin is enabled for the site

2. **Check logger**:
   - Click uBlock icon
   - Click logger button
   - See what's being blocked/allowed

3. **Disable other extensions**:
   - Other ad blockers may conflict
   - Disable and test

4. **Check filter syntax**:
   - Custom filters should be one domain per line
   - No special characters needed

## Performance Issues

### Slow DNS Queries

**Symptoms**: DNS resolution taking >100ms

**Common Solutions**:

1. **Check upstream DNS**:
```bash
dig @1.1.1.1 google.com +stats
```

2. **Increase cache size** (platform-specific)

3. **Check network latency**:
```bash
ping 1.1.1.1
traceroute 1.1.1.1
```

4. **Monitor query load**:
```bash
# Platform-specific monitoring commands
```

### High CPU Usage

**Symptoms**: DNS server using excessive CPU

**Solutions**:

1. **Check query rate**:
   - Unusual spike might indicate attack
   - Check logs for patterns

2. **Optimize configuration**:
   - Reduce logging verbosity
   - Increase cache TTL
   - Use faster upstream DNS

3. **Check for loops**:
   - Ensure no DNS forwarding loops
   - Verify upstream DNS is different

## False Positives

### Legitimate Domain Blocked

**Symptoms**: Important site not accessible

**Immediate Fix**:

1. **Whitelist the domain**:

**Pi-Hole**:
```bash
pihole -w example.com
```

**AdGuard Home**:
- Go to Filters → Custom filtering rules
- Add: `@@||example.com^`

**Squid**:
Add to whitelist file before blacklist ACL

**Unbound/BIND**:
Remove from blacklist file and reload

**uBlock Origin**:
- Click uBlock icon
- Click power button to disable for site

**Long-term Fix**:

1. **Report false positive**:
   - Go to [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)
   - Use "Whitelist Request" template
   - Provide domain and justification

2. **Maintain local whitelist**:
   - Keep a local whitelist file
   - Update after each blacklist update

## Getting Help

If you can't resolve your issue:

1. **Check existing issues**:
   - [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)
   - Search for similar problems

2. **Gather information**:
   - Platform and version
   - Blacklist version/date
   - Error messages
   - Relevant logs
   - Steps to reproduce

3. **Create new issue**:
   - Use appropriate template
   - Provide all gathered information
   - Be specific and detailed

4. **Community support**:
   - Platform-specific forums (Pi-Hole Discourse, etc.)
   - Reddit communities
   - Stack Overflow

## Preventive Measures

- ✅ Keep software updated
- ✅ Monitor logs regularly
- ✅ Test after updates
- ✅ Maintain local whitelist
- ✅ Document custom configurations
- ✅ Have rollback plan
- ✅ Monitor performance metrics

For more information, see:
- [TESTING.md](TESTING.md) - Testing procedures
- [MAINTENANCE.md](MAINTENANCE.md) - Maintenance guide
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization
