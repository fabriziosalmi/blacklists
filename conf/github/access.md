### Compatibility
- **Windows**, **Mac**, **Linux** via the [uBlock Origin](https://github.com/gorhill/uBlock#ublock-origin) browser extension ([Firefox](https://addons.mozilla.org/it/firefox/addon/ublock-origin/) or [others browsers](https://ublockorigin.com))
- **iPhone** (Safari + DNS) via [AdGuard Pro for IOS](https://download.adguard.com/d/18672/ios-pro?exid=3ail29lmsdyc84s84c0gkosgo)
- **Android** via [AdGuard Pro for Android](https://adguard.com/it/adguard-android/overview.html)
- [PiHole](https://pi-hole.net/), [AdGuard Home](https://adguard.com/it/adguard-home/overview.html) and [Unbound](https://github.com/fabriziosalmi/blacklists/releases/tag/latest) **DNS filtering applications**
- **Proxies** like [Squid](http://www.squid-cache.org/), **firewalls** like [nftables](https://github.com/fabriziosalmi/blacklists/blob/main/scripts/nft_blacklist_fqdn.sh) and **WAF** like [OPNsense](https://docs.opnsense.org/manual/how-tos/proxywebfilter.html)
- **DNS servers** like [BIND9](https://github.com/fabriziosalmi/blacklists/tree/main/docs#how-to-implement-the-rpz-blacklist-with-bind9) or [PowerDNS](https://github.com/PowerDNS/pdns)
  
### Features
- **Hourly Updates**: Stay protected against emerging threats
- **Comprehensive Coverage**: Aggregated from the most frequently updated blacklists ([more info](https://github.com/fabriziosalmi/blacklists/blob/main/docs/blacklists_reviews.md))
- **Broad Compatibility**: Works across browsers, firewalls, proxies, and more
- **Robust Security**: Protect against phishing, spam, scams, ads, trackers, bad websites and more
- **Whitelist Capability**: [Submit one or more domains for whitelisting](https://github.com/fabriziosalmi/blacklists/issues/new/choose)
- **Local Mirror**: Set up easily using the [Docker image](https://hub.docker.com/repository/docker/fabriziosalmi/blacklists/)
- **Machine Learning**: Detect bad domain names with a [simple FQDN Classifier](https://github.com/fabriziosalmi/fqdn-model) trained on this blacklist
