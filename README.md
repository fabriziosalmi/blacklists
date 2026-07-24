# Domains Blacklist

Daily updated domains blacklist.

## Downloads
- Pi-Hole, AdGuard, uBlock Origin: 
```
https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```

- Squid: **[blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt)** 
- Unbound: **[unbound_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt)** 
- Bind, PowerDNS (RPZ): **[rpz_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt)** 


![Static Badge](https://img.shields.io/badge/blacklists-50-000000) ![Static Badge](https://img.shields.io/badge/blacklisted-4671860-cc0000) ![Static Badge](https://img.shields.io/badge/whitelisted-2059-00CC00) ![Static Badge](https://img.shields.io/badge/streaming_blacklist-28107-000000) ![GitHub issues](https://img.shields.io/github/issues/fabriziosalmi/blacklists)
<!-- STATS_START -->
## Daily Statistics

**Last Updated**: 2026-07-24 01:40 UTC

| Metric | Value |
|--------|-------|
| **Total Domains** | **4,671,860** |
| **Whitelisted** | 2,059 |
| **Sources** | 50 |
| **Daily Change** | +53,318 (+1.15%) |
| **Weekly Change** | -243,245 (-4.95%) |
| **Monthly Change** | +199,391 (+4.46%) |

![Trend Chart](stats/trend.png)

*Statistics are automatically updated daily at midnight UTC*

<!-- STATS_END -->
### Compatibility
- **Windows**, **Mac**, **Linux** via the [uBlock Origin](https://github.com/gorhill/uBlock#ublock-origin) browser extension ([Firefox](https://addons.mozilla.org/it/firefox/addon/ublock-origin/) or [others browsers](https://ublockorigin.com))
- **iPhone** (Safari + DNS) via [AdGuard Pro for IOS](https://download.adguard.com/d/18672/ios-pro?exid=3ail29lmsdyc84s84c0gkosgo)
- **Android** via [AdGuard Pro for Android](https://adguard.com/it/adguard-android/overview.html)
- [PiHole](https://pi-hole.net/), [AdGuard Home](https://adguard.com/it/adguard-home/overview.html) and [Unbound](https://github.com/fabriziosalmi/blacklists/releases/tag/latest) **DNS filtering applications**
- **Proxies** like [Squid](http://www.squid-cache.org/), **firewalls** like [nftables](https://github.com/fabriziosalmi/blacklists/blob/main/scripts/nft_blacklist_fqdn.sh) and **WAF** like [OPNsense](https://docs.opnsense.org/manual/how-tos/proxywebfilter.html)
- **DNS servers** like [BIND9](https://github.com/fabriziosalmi/blacklists/tree/main/docs#how-to-implement-the-rpz-blacklist-with-bind9) or [PowerDNS](https://github.com/PowerDNS/pdns)
  
### Features
- **Daily Updates**: Aggregated and deduplicated daily from all configured sources
- **Multiple Formats**: Plain domain list (`blacklist.txt`), Unbound (`unbound_blacklist.txt`), BIND9 RPZ (`rpz_blacklist.txt`)
- **Broad Compatibility**: Works with Pi-Hole, AdGuard Home, Unbound, BIND9, Squid, nftables, uBlock Origin, and more
- **Whitelist Support**: [Submit domains for whitelisting](https://github.com/fabriziosalmi/blacklists/issues/new/choose)
- **Local Mirror**: Deploy using the [Docker image](https://hub.docker.com/repository/docker/fabriziosalmi/blacklists/)
- **FQDN Classifier**: A machine learning model to [predict bad domains](https://github.com/fabriziosalmi/fqdn-model) trained on this blacklist

## Contribute

- Propose additions or removals to the blacklist
- Enhance blacklist or whitelist processing
- Improve statistics and data analytics

## Credits

This project would not exist without the maintainers of the upstream lists it
aggregates. Every source is redistributed under its own license. The full
per-source license and attribution map lives in **[SOURCES.md](SOURCES.md)**.

Upstream sources currently aggregated:

[LanikSJ/ubo-filters](https://github.com/LanikSJ/ubo-filters) ·
[dmachard/blocklist-domains](https://github.com/dmachard/blocklist-domains) ·
[uBlockOrigin/uAssets](https://github.com/uBlockOrigin/uAssets) ·
[Matomo referrer-spam-blacklist](https://github.com/matomo-org/referrer-spam-blacklist) ·
[What-Zit-Tooya/Ad-Block](https://github.com/What-Zit-Tooya/Ad-Block) ·
[quidsup/notrack](https://gitlab.com/quidsup/notrack-blocklists) ·
[CERT Polska (cert.pl)](https://hole.cert.pl) ·
[Geoffrey Frogeye](https://hostfiles.frogeye.fr) ·
[malware-filter](https://gitlab.com/malware-filter) ·
[Peter Lowe (pgl.yoyo.org)](https://pgl.yoyo.org/adservers/) ·
[DandelionSprout/adfilt](https://github.com/DandelionSprout/adfilt) ·
[PolishFiltersTeam/KADhosts](https://gitlab.com/PolishFiltersTeam/KADhosts) ·
[azet12/KADhosts](https://github.com/azet12/KADhosts) ·
[ShadowWhisperer](https://github.com/ShadowWhisperer/BlockLists) ·
[StevenBlack/hosts](https://github.com/StevenBlack/hosts) ·
[badmojr/1Hosts](https://github.com/badmojr/1Hosts) ·
[bigdargon/hostsVN](https://github.com/bigdargon/hostsVN) ·
[durablenapkin/scamblocklist](https://github.com/durablenapkin/scamblocklist) ·
[hagezi/dns-blocklists](https://github.com/hagezi/dns-blocklists) ·
[mitchellkrogza](https://github.com/mitchellkrogza) ·
[phishfort](https://github.com/phishfort/phishfort-lists) ·
[stamparm/blackbook](https://github.com/stamparm/blackbook) ·
[oisd](https://oisd.nl) ·
[lightswitch05 (developerdan)](https://github.com/lightswitch05/hosts) ·
[malwareworld.com](https://malwareworld.com) ·
[ThioJoe/YT-Spam-Lists](https://github.com/ThioJoe/YT-Spam-Lists) ·
[phishunt.io](https://phishunt.io) ·
[jarelllama/Scam-Blocklist](https://github.com/jarelllama/Scam-Blocklist) ·
[AdGuard](https://github.com/AdguardTeam/AdGuardSDNSFilter), [EasyList](https://easylist.to) and [UT1 Toulouse](https://dsi.ut-capitole.fr/blacklists/) (via [firebog](https://firebog.net))

For the complete list of feed URLs, see [blacklists.fqdn.urls](https://github.com/fabriziosalmi/blacklists/blob/main/blacklists.fqdn.urls). For licenses and attribution, see [SOURCES.md](SOURCES.md).

Code improvements by [xRuffKez](https://github.com/xRuffKez), [hulores](https://github.com/hulores) and other contributors.

## License

The **aggregation tooling** in this repository (`generate.py`, `generate.sh`,
`sanitize.py`, `whitelist.py`, `check_whitelist.py`, and the helper scripts) is
licensed under the **GNU General Public License v3.0** (see [`LICENSE`](LICENSE)).

The generated **`blacklist.txt`** (and the derived `rpz_blacklist.txt` and
`unbound_blacklist.txt`) is **not** covered by that license. It is an **aggregate**
that redistributes third-party domain lists, each under its own license and terms.
The published file carries an attribution header and points to
**[SOURCES.md](SOURCES.md)**, which maps every source to its license and the
attribution it requires.

If you are a rights holder and want a list changed or removed, please
[open an issue](https://github.com/fabriziosalmi/blacklists/issues/new/choose).
