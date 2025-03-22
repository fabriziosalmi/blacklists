# Domains Blacklist

**Hourly updated domains blacklist** 🚫

> _"Building a service on top of a regularly updated blacklist can provide immense value, not only for individual internet users but also for businesses and cybersecurity professionals. Whatever service you choose to build, ensure it's user-friendly, reliable, and secure."_

## ✅ Downloads
- Pi-Hole, AdGuard, uBlock Origin: 
```
https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```

- Squid: **[blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt)** 
- Unbound: **[unbound_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt)** 
- Bind, PowerDNS (RPZ): **[rpz_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt)** 




![Static Badge](https://img.shields.io/badge/blacklists-61-000000) ![Static Badge](https://img.shields.io/badge/blacklisted-2943292-cc0000) ![Static Badge](https://img.shields.io/badge/whitelisted-2253-00CC00) ![Static Badge](https://img.shields.io/badge/streaming_blacklist-28107-000000) ![GitHub issues](https://img.shields.io/github/issues/fabriziosalmi/blacklists)
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
## 👨‍💻 Contribute

- Propose additions or removals to the blacklist
- Enhance blacklist or whitelist processing
- Dive into statistics and data analytics
## 🏅 Credits

This project owes its existence to numerous dedicated blacklist creators such as:

[T145/BlackMirror](https://github.com/T145/black-mirror) - [Fabrice Prigent (UT1 mirror)](https://github.com/olbat/ut1-blacklists) - [1hosts](https://badmojr.gitlab.io/1hosts/Lite/domains.txt) - [PolishFiltersTeam](https://gitlab.com/PolishFiltersTeam/) - [ShadowWhisperer](https://raw.githubusercontent.com/ShadowWhisperer/BlockLists/) - [StevenBlack](https://raw.githubusercontent.com/StevenBlack/hosts/) - [bigdargon](https://raw.githubusercontent.com/bigdargon/hostsVN/master/hosts) - [developerdan](https://www.github.developerdan.com/) - [firebog](https://v.firebog.net/hosts/AdguardDNS.txt) - [hagezi](https://gitlab.com/hagezi/) - [malware-filter](https://malware-filter.gitlab.io/) - [phishfort](https://raw.githubusercontent.com/phishfort/phishfort-lists/master/blacklists/domains.json) - [phishing.army](https://phishing.army/) - [quidsup](https://gitlab.com/quidsup/) - [DandelionSprout](https://raw.githubusercontent.com/DandelionSprout/adfilt/) - [RPiList](https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/) - [What-Zit-Tooya](https://github.com/What-Zit-Tooya/Ad-Block) - [azet12](https://raw.githubusercontent.com/azet12/KADhosts) - [cert.pl](https://hole.cert.pl) - [mitchellkrogza](https://raw.githubusercontent.com/mitchellkrogza/Ultimate.Hosts.Blacklist) - [o0.pages.dev](https://o0.pages.dev) - [pgl.yoyo.org](https://pgl.yoyo.org/) - [lightswitch05](https://raw.githubusercontent.com/lightswitch05/hosts/) - [frogeye.fr](https://hostfiles.frogeye.fr/) - [fruxlabs](https://rescure.fruxlabs.com/) - [durablenapkin](https://raw.githubusercontent.com/durablenapkin/scamblocklist/) - [digitalside.it](https://osint.digitalside.it/Threat-Intel/lists/latestdomains.txt) - [malwareworld.com](https://malwareworld.com/)

and many more.

For a full list, check the [complete blacklists URLs](https://github.com/fabriziosalmi/blacklists/blob/main/blacklists.fqdn.urls).

Code improvements by [xRuffKez](https://github.com/xRuffKez).
## 👨‍💻 Machine Learning

- Machine learning model to [predict bad domains](https://github.com/fabriziosalmi/fqdn-model)
## 🗓️ Roadmap

2025

- Improve blacklist
- Improve whitelist
---
![Static Badge](https://img.shields.io/badge/DomainsBlacklists-For_a_safer_digital_experience-00ce00?style=for-the-badge)
