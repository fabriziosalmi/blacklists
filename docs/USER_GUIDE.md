# User Guide

This guide provides comprehensive instructions for using the blacklists project.

## Overview

The Domains Blacklist is a curated, **daily-updated** collection of malicious, advertising, tracking, and unwanted domains. It's designed to work with various platforms including DNS servers, proxies, firewalls, and browser extensions.

## Quick Start

### For Home Users

**Recommended**: Pi-Hole or AdGuard Home

1. Install [Pi-Hole](https://pi-hole.net/) or [AdGuard Home](https://adguard.com/en/adguard-home/overview.html)
2. Add blacklist URL: `https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt`
3. Update and enjoy ad-free browsing

### For Browser Users

**Recommended**: uBlock Origin

1. Install [uBlock Origin](https://ublockorigin.com/)
2. Add custom filter list
3. Paste URL: `https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt`

### For Advanced Users

Choose based on your infrastructure:
- **Unbound**: Recursive DNS server
- **BIND9**: Enterprise DNS with RPZ support
- **Squid**: HTTP/HTTPS proxy
- **nftables**: Firewall-level blocking

## Installation by Platform

### Pi-Hole

**Requirements**:
- Raspberry Pi or Linux server
- Pi-Hole installed

**Steps**:

1. **Access Pi-Hole Admin**:
   - Navigate to `http://pi.hole/admin`
   - Or `http://<your-pi-ip>/admin`

2. **Add Blacklist**:
   - Go to **Adlists**
   - Click **Add new adlist**
   - Enter URL:
     ```
     https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
     ```
   - Click **Add**

3. **Update Gravity**:
   - Go to **Tools** → **Update Gravity**
   - Click **Update**
   - Wait for completion (2-5 minutes)

4. **Verify**:
   - Go to **Dashboard**
   - Check "Domains on Blocklist" count
   - Should show ~3 million domains

**Command Line**:
```bash
# Add blacklist
sqlite3 /etc/pihole/gravity.db \
  "INSERT INTO adlist (address, enabled) \
   VALUES ('https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt', 1);"

# Update gravity
pihole -g
```

### AdGuard Home

**Requirements**:
- Linux/Windows/macOS server
- AdGuard Home installed

**Steps**:

1. **Access AdGuard Home**:
   - Navigate to `http://<your-server-ip>:3000`

2. **Add Blacklist**:
   - Go to **Filters** → **DNS blocklists**
   - Click **Add blocklist**
   - Enter:
     - **Name**: Domains Blacklist
     - **URL**: `https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt`
   - Click **Save**

3. **Update Filters**:
   - Click **Update filters** button
   - Wait for completion

4. **Verify**:
   - Check filter count in dashboard
   - Should show ~3 million rules

### Squid Proxy

**Requirements**:
- Linux server
- Squid installed

**Steps**:

1. **Download Blacklist**:
```bash
sudo mkdir -p /etc/squid/conf.d
sudo wget -O /etc/squid/conf.d/blacklist.txt \
  https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```

2. **Configure Squid**:

Edit `/etc/squid/squid.conf`:
```conf
# Add before http_access rules
acl blacklist dstdomain "/etc/squid/conf.d/blacklist.txt"
http_access deny blacklist

# Your other rules here
http_access allow localnet
http_access deny all
```

3. **Test Configuration**:
```bash
sudo squid -k parse
```

4. **Reload Squid**:
```bash
sudo systemctl reload squid
```

5. **Verify**:
```bash
# Test blocked domain
curl -x http://localhost:3128 http://doubleclick.net
# Should return 403 Forbidden
```

**Auto-Update Script**:

Create `/etc/cron.daily/update-squid-blacklist`:
```bash
#!/bin/bash
wget -O /etc/squid/conf.d/blacklist.txt.new \
  https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt

if [ $? -eq 0 ]; then
  mv /etc/squid/conf.d/blacklist.txt.new /etc/squid/conf.d/blacklist.txt
  squid -k reconfigure
fi
```

Make executable:
```bash
sudo chmod +x /etc/cron.daily/update-squid-blacklist
```

### Unbound DNS

**Requirements**:
- Linux server
- Unbound installed

**Steps**:

1. **Download Blacklist**:
```bash
sudo wget -O /etc/unbound/unbound_blacklist.txt \
  https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt
```

2. **Configure Unbound**:

Edit `/etc/unbound/unbound.conf`:
```conf
server:
    # Include blacklist
    include: /etc/unbound/unbound_blacklist.txt
    
    # Other configuration
    verbosity: 1
    interface: 0.0.0.0
    port: 53
    do-ip4: yes
    do-ip6: yes
    do-udp: yes
    do-tcp: yes
```

3. **Test Configuration**:
```bash
sudo unbound-checkconf
```

4. **Reload Unbound**:
```bash
sudo systemctl reload unbound
```

5. **Verify**:
```bash
dig @127.0.0.1 doubleclick.net
# Should return NXDOMAIN or static response
```

**Auto-Update Script**:

Create `/etc/cron.daily/update-unbound-blacklist`:
```bash
#!/bin/bash
wget -O /etc/unbound/unbound_blacklist.txt.new \
  https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt

if [ $? -eq 0 ]; then
  mv /etc/unbound/unbound_blacklist.txt.new /etc/unbound/unbound_blacklist.txt
  unbound-control reload
fi
```

### BIND9 with RPZ

**Requirements**:
- Linux server
- BIND9 installed

**Steps**:

1. **Download RPZ Blacklist**:
```bash
sudo wget -O /etc/bind/rpz_blacklist.txt \
  https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt
```

2. **Configure BIND9**:

Edit `/etc/bind/named.conf.local`:
```conf
zone "rpz.blacklist" {
    type master;
    file "/etc/bind/rpz_blacklist.txt";
};
```

Edit `/etc/bind/named.conf.options`:
```conf
options {
    // Other options...
    
    response-policy {
        zone "rpz.blacklist";
    };
};
```

3. **Check Configuration**:
```bash
sudo named-checkconf
sudo named-checkzone rpz.blacklist /etc/bind/rpz_blacklist.txt
```

4. **Reload BIND**:
```bash
sudo systemctl reload bind9
```

5. **Verify**:
```bash
dig @localhost doubleclick.net
# Should return NXDOMAIN
```

### uBlock Origin

**Requirements**:
- Firefox, Chrome, or Edge browser
- uBlock Origin extension

**Steps**:

1. **Install uBlock Origin**:
   - [Firefox](https://addons.mozilla.org/firefox/addon/ublock-origin/)
   - [Chrome](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm)
   - [Edge](https://microsoftedge.microsoft.com/addons/detail/ublock-origin/odfafepnkmbhccpbejgmiehpchacaeak)

2. **Open Dashboard**:
   - Click uBlock Origin icon
   - Click settings icon (⚙️)

3. **Add Custom Filter**:
   - Go to **Filter lists** tab
   - Scroll to bottom
   - Under "Import", paste:
     ```
     https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
     ```
   - Click **Apply changes**

4. **Update Filters**:
   - Click **Update now** at top
   - Wait for completion

5. **Verify**:
   - Visit a site with ads
   - Check uBlock logger (click icon → logger)
   - Should see blocked requests

## Usage

### Daily Updates

The blacklist is **automatically updated daily at midnight UTC**. No manual intervention required.

**Why daily?**
- Balances freshness with resource efficiency
- Keeps the service free for everyone
- Sufficient for most threat landscapes

### Checking for Updates

**Pi-Hole**:
```bash
pihole -g
```

**AdGuard Home**:
- Dashboard → Filters → Update filters

**Manual Download**:
```bash
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```

### Whitelisting Domains

If a legitimate domain is blocked:

**Pi-Hole**:
```bash
pihole -w example.com
```

**AdGuard Home**:
- Filters → Custom filtering rules
- Add: `@@||example.com^`

**Squid**:
Create whitelist file and add ACL before blacklist

**Unbound/BIND**:
Remove domain from blacklist file

**uBlock Origin**:
- Click uBlock icon on the site
- Click power button to disable

**Submit for Global Whitelist**:
- [Create issue](https://github.com/fabriziosalmi/blacklists/issues/new/choose)
- Use "Whitelist Request" template

### Monitoring

**Pi-Hole**:
- Dashboard shows blocked queries
- Query log shows individual blocks

**AdGuard Home**:
- Dashboard shows statistics
- Query log shows details

**Squid**:
```bash
tail -f /var/log/squid/access.log | grep DENIED
```

**Unbound**:
```bash
sudo unbound-control stats_noreset
```

**BIND9**:
```bash
sudo rndc stats
cat /var/cache/bind/named.stats | grep RPZ
```

## Advanced Usage

### Local Mirror

Run your own blacklist mirror:

```bash
docker pull fabriziosalmi/blacklists:latest
docker run -d -p 8080:80 fabriziosalmi/blacklists

# Access at http://localhost:8080/blacklist.txt
```

### Custom Blacklist Generation

Generate your own blacklist:

```bash
# Clone repository
git clone https://github.com/fabriziosalmi/blacklists.git
cd blacklists

# Edit sources
nano blacklists.fqdn.urls

# Generate
bash generate.sh

# Result in all.fqdn.blacklist
```

### Integration with Other Tools

**Firewall (nftables)**:
```bash
# Use provided script
bash scripts/nft_blacklist_fqdn.sh
```

**Machine Learning**:
- Use [FQDN Classifier](https://github.com/fabriziosalmi/fqdn-model)
- Trained on this blacklist

## Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Quick Checks**:

1. **Blacklist not working**:
   - Verify URL is correct
   - Check platform is using correct DNS
   - Test with known bad domain

2. **Performance issues**:
   - See [PERFORMANCE.md](PERFORMANCE.md)
   - Increase cache size
   - Use faster upstream DNS

3. **False positives**:
   - Whitelist the domain
   - Report issue on GitHub

## Best Practices

- ✅ Keep platform software updated
- ✅ Monitor blocked queries regularly
- ✅ Maintain local whitelist
- ✅ Test after updates
- ✅ Use appropriate format for your platform
- ✅ Enable caching for better performance
- ✅ Have backup DNS configured

## Getting Help

- **Documentation**: [docs/](https://github.com/fabriziosalmi/blacklists/tree/main/docs)
- **Issues**: [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)
- **Discussions**: [GitHub Discussions](https://github.com/fabriziosalmi/blacklists/discussions)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Reporting issues
- Suggesting improvements
- Submitting whitelist requests
- Contributing code

## Additional Resources

- [TESTING.md](TESTING.md) - Testing procedures
- [MAINTENANCE.md](MAINTENANCE.md) - Maintenance guide
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization
- [DEVOPS.md](DEVOPS.md) - DevOps and automation