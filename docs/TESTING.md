# Testing Guide

This guide provides instructions for testing the blacklists in various environments.

## Quick Test

### Verify a Domain is Blocked

The simplest way to test if a domain is in the blacklist:

```bash
# Download the blacklist
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt

# Search for a domain
grep "example-malware.com" blacklist.txt
```

## Platform-Specific Testing

### Pi-Hole

#### Test After Adding Blacklist

1. **Add the blacklist** (see [docs/README.md](README.md#pihole))

2. **Update Gravity**:
```bash
pihole -g
```

3. **Test a known bad domain**:
```bash
# Using dig
dig @192.168.1.1 doubleclick.net

# Should return 0.0.0.0 or your Pi-Hole IP
```

4. **Check Pi-Hole logs**:
```bash
pihole -t
# Then visit a website with ads/trackers
```

5. **Verify in Web UI**:
   - Go to http://pi.hole/admin
   - Check Query Log
   - Look for blocked queries

### AdGuard Home

#### Test After Adding Blacklist

1. **Add the blacklist** (see [docs/README.md](README.md#adguard-home))

2. **Test DNS resolution**:
```bash
# Using nslookup
nslookup doubleclick.net 192.168.1.1

# Should return blocked/filtered response
```

3. **Check AdGuard logs**:
   - Go to AdGuard Home dashboard
   - Navigate to Query Log
   - Filter by "Blocked by filters"

4. **Test with curl**:
```bash
# Should fail or return blocked page
curl -v http://doubleclick.net
```

### Squid Proxy

#### Test After Configuration

1. **Configure Squid** (see [docs/README.md](README.md#squid))

2. **Test via proxy**:
```bash
# Set proxy
export http_proxy="http://192.168.1.1:3128"
export https_proxy="http://192.168.1.1:3128"

# Try to access blocked domain
curl -v http://doubleclick.net

# Should return 403 Forbidden
```

3. **Check Squid logs**:
```bash
tail -f /var/log/squid/access.log | grep DENIED
```

4. **Test bypass attempt**:
```bash
# Try direct IP (should also be blocked if configured)
curl -v http://142.250.185.206

# Should be denied if IP blocking is enabled
```

### Unbound DNS

#### Test After Configuration

1. **Configure Unbound** (see [docs/README.md](README.md#implementing-the-blacklist))

2. **Reload configuration**:
```bash
sudo unbound-control reload
```

3. **Test DNS query**:
```bash
dig @127.0.0.1 doubleclick.net

# Should return NXDOMAIN or static response
```

4. **Check Unbound stats**:
```bash
unbound-control stats_noreset | grep num.query
```

5. **Verbose testing**:
```bash
# Enable verbose logging temporarily
sudo unbound-control verbosity 3

# Make test query
dig @127.0.0.1 ads.example.com

# Check logs
sudo tail -f /var/log/unbound/unbound.log

# Disable verbose logging
sudo unbound-control verbosity 1
```

### BIND9 RPZ

#### Test After Configuration

1. **Configure BIND9 RPZ** (see [docs/README.md](README.md#how-to-implement-the-rpz-blacklist-with-bind9))

2. **Check configuration**:
```bash
sudo named-checkconf
sudo named-checkzone rpz.blacklist /path/to/rpz_blacklist.txt
```

3. **Reload BIND**:
```bash
sudo rndc reload
```

4. **Test DNS query**:
```bash
dig @localhost doubleclick.net

# Should return NXDOMAIN or RPZ response
```

5. **Check RPZ statistics**:
```bash
sudo rndc stats
cat /var/cache/bind/named.stats | grep RPZ
```

6. **Test with specific query types**:
```bash
# Test A record
dig @localhost doubleclick.net A

# Test AAAA record
dig @localhost doubleclick.net AAAA

# Both should be blocked
```

### uBlock Origin

#### Test After Adding List

1. **Add the blacklist** (see [docs/README.md](README.md#linux-windows-osx-and-any-device-with-a-browser-able-to-install-the-ublock-origin-extension))

2. **Force update**:
   - Open uBlock Origin dashboard
   - Go to "Filter lists"
   - Click "Update now"

3. **Test on a website**:
   - Visit a site with ads (e.g., news sites)
   - Open browser DevTools (F12)
   - Check Network tab for blocked requests

4. **Check uBlock logger**:
   - Click uBlock icon
   - Click "Logger" button
   - Browse websites and see blocked requests in real-time

5. **Test specific domain**:
   - Open logger
   - Try to visit `http://doubleclick.net`
   - Should see blocked entry in logger

## Automated Testing

### Test Script for DNS-based Solutions

Create a test script `test_blacklist.sh`:

```bash
#!/bin/bash

# Configuration
DNS_SERVER="192.168.1.1"  # Your DNS server IP
TEST_DOMAINS=(
    "doubleclick.net"
    "googleadservices.com"
    "facebook.com"  # Should NOT be blocked (test false positive)
)

echo "Testing DNS Blacklist on $DNS_SERVER"
echo "========================================"

for domain in "${TEST_DOMAINS[@]}"; do
    echo -n "Testing $domain... "
    
    result=$(dig @$DNS_SERVER $domain +short)
    
    if [ -z "$result" ] || [ "$result" == "0.0.0.0" ]; then
        echo "✓ BLOCKED"
    else
        echo "✗ ALLOWED ($result)"
    fi
done
```

Run the test:
```bash
chmod +x test_blacklist.sh
./test_blacklist.sh
```

### Python Test Script

Create `test_blacklist.py`:

```python
#!/usr/bin/env python3
import dns.resolver
import sys

DNS_SERVER = '192.168.1.1'
TEST_DOMAINS = [
    ('doubleclick.net', True),  # Should be blocked
    ('googleadservices.com', True),  # Should be blocked
    ('google.com', False),  # Should NOT be blocked
    ('github.com', False),  # Should NOT be blocked
]

def test_domain(domain, should_block):
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [DNS_SERVER]
    
    try:
        answers = resolver.resolve(domain, 'A')
        ips = [str(rdata) for rdata in answers]
        
        if '0.0.0.0' in ips or not ips:
            blocked = True
        else:
            blocked = False
            
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        blocked = True
    except Exception as e:
        print(f"Error testing {domain}: {e}")
        return False
    
    success = (blocked == should_block)
    status = "✓" if success else "✗"
    block_status = "BLOCKED" if blocked else "ALLOWED"
    expected = "should block" if should_block else "should allow"
    
    print(f"{status} {domain}: {block_status} ({expected})")
    return success

if __name__ == '__main__':
    print(f"Testing DNS Blacklist on {DNS_SERVER}")
    print("=" * 50)
    
    results = [test_domain(domain, should_block) 
               for domain, should_block in TEST_DOMAINS]
    
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    sys.exit(0 if passed == total else 1)
```

Run the test:
```bash
pip install dnspython
python3 test_blacklist.py
```

## Performance Testing

### DNS Query Performance

Test query response time:

```bash
# Single query
time dig @192.168.1.1 example.com

# Multiple queries
for i in {1..100}; do
    dig @192.168.1.1 test$i.example.com > /dev/null
done
```

### Load Testing

Use `dnsperf` for load testing:

```bash
# Install dnsperf
sudo apt-get install dnsperf  # Debian/Ubuntu
brew install dnsperf          # macOS

# Create query file
cat > queries.txt << EOF
doubleclick.net A
googleadservices.com A
google.com A
github.com A
EOF

# Run performance test
dnsperf -d queries.txt -s 192.168.1.1 -l 30
```

## Integration Testing

### Test with Real Browsers

1. **Configure browser to use DNS server**:
   - Set system DNS to your DNS server
   - Or configure browser-specific DNS (Firefox, Chrome)

2. **Visit test sites**:
   - News sites with ads
   - Sites known for trackers
   - Legitimate sites (should work normally)

3. **Check browser console**:
   - Open DevTools (F12)
   - Look for blocked requests
   - Verify legitimate requests work

### Test with Mobile Devices

1. **Configure mobile DNS**:
   - iOS: Settings > Wi-Fi > DNS
   - Android: Settings > Network > Private DNS

2. **Test apps**:
   - Open apps with ads
   - Verify ads are blocked
   - Ensure apps function normally

## Validation Testing

### Verify Blacklist Integrity

```bash
# Download blacklist
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt

# Check format (should be one domain per line)
head -n 10 blacklist.txt

# Count total domains
wc -l blacklist.txt

# Check for duplicates
sort blacklist.txt | uniq -d

# Validate domain format
grep -v -E '^[a-z0-9.-]+\.[a-z]{2,}$' blacklist.txt
# Should return nothing if all domains are valid
```

### Test Different Formats

```bash
# Test standard format
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt

# Test Unbound format
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt
grep -c "local-zone:" unbound_blacklist.txt

# Test RPZ format
wget https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt
grep -c "CNAME \." rpz_blacklist.txt
```

## Troubleshooting Tests

### DNS Not Resolving

```bash
# Check DNS server is running
sudo systemctl status pihole-FTL  # Pi-Hole
sudo systemctl status AdGuardHome  # AdGuard
sudo systemctl status unbound      # Unbound
sudo systemctl status named        # BIND9

# Check DNS server is listening
sudo netstat -tulpn | grep :53

# Test DNS server directly
dig @127.0.0.1 google.com
```

### Domains Not Being Blocked

```bash
# Verify blacklist is loaded
pihole -g -r rebuild  # Pi-Hole
sudo rndc reload       # BIND9
sudo unbound-control reload  # Unbound

# Check blacklist file exists and is not empty
ls -lh /etc/pihole/gravity.db  # Pi-Hole
ls -lh /path/to/rpz_blacklist.txt  # BIND9

# Verify domain is in blacklist
grep "doubleclick.net" /path/to/blacklist.txt
```

## Continuous Testing

### Automated Daily Tests

Create a cron job for daily testing:

```bash
# Add to crontab
crontab -e

# Add line (runs daily at 2 AM)
0 2 * * * /path/to/test_blacklist.sh > /var/log/blacklist_test.log 2>&1
```

### Monitoring

Set up monitoring to alert on:
- Blacklist update failures
- High number of false positives
- DNS query failures
- Performance degradation

## Reporting Issues

If you find issues during testing:

1. **Gather information**:
   - Platform and version
   - Blacklist version/date
   - Specific domain causing issues
   - Expected vs actual behavior

2. **Create an issue**:
   - Go to [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)
   - Use the appropriate template
   - Include test results and logs

3. **For false positives**:
   - Submit whitelist request
   - Include justification
   - Provide domain category

## Best Practices

- ✅ Test after every update
- ✅ Maintain a list of test domains
- ✅ Test both blocking and allowing
- ✅ Monitor performance regularly
- ✅ Keep test scripts updated
- ✅ Document test results
- ✅ Automate where possible

For more information, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).