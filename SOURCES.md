# Sources and Licenses

This project is an **aggregator**. The published `blacklist.txt` (and the
derived `rpz_blacklist.txt` and `unbound_blacklist.txt`) is a compilation of
domain lists produced by third parties. Each upstream list remains the property
of its authors and is redistributed here **under its own license and terms**,
listed below.

The aggregation tooling in this repository (`generate.py`, `generate.sh`,
`sanitize.py`, `whitelist.py`, `check_whitelist.py`, and the helper scripts) is
licensed under **GPL-3.0** (see [`LICENSE`](LICENSE) and the License section of
the [README](README.md)). That license covers the code, **not** the aggregated
data, which stays under the licenses on this page.

The list of upstream feeds is maintained in
[`blacklists.fqdn.urls`](blacklists.fqdn.urls). If you are a rights holder and
want a change or removal, please open an issue.

Attribution key:
- **Permissive** (MIT / Apache-2.0 / BSD / custom permissive): keep the
  copyright and license notice.
- **Copyleft** (GPL-3.0 / MPL-2.0): keep copyright and license, preserve the
  same license on redistribution, keep the source available.
- **Share-alike** (CC BY-SA / CC BY): give credit and redistribute under the
  same license.
- **Public domain** (CC0 / Unlicense / PD): no attribution legally required
  (credit still given here as a courtesy).

---

## Permissive (attribution required)

| Source | Upstream (owner / URL) | License | Attribution |
|---|---|---|---|
| ubo-filters | LanikSJ - https://github.com/LanikSJ/ubo-filters | MIT | Keep notice |
| blocklist-domains | dmachard - https://github.com/dmachard/blocklist-domains | MIT | Keep notice |
| Ad-Block | What-Zit-Tooya - https://github.com/What-Zit-Tooya/Ad-Block | MIT | Keep notice |
| hosts | StevenBlack - https://github.com/StevenBlack/hosts | MIT | Keep notice |
| hostsVN | bigdargon - https://github.com/bigdargon/hostsVN | MIT | Keep notice |
| scamblocklist | durablenapkin - https://github.com/durablenapkin/scamblocklist | MIT | Keep notice |
| Ultimate.Hosts.Blacklist | mitchellkrogza - https://github.com/mitchellkrogza/Ultimate.Hosts.Blacklist | MIT | Keep notice |
| The-Big-List-of-Hacked-Malware-Web-Sites | mitchellkrogza - https://github.com/mitchellkrogza/The-Big-List-of-Hacked-Malware-Web-Sites | MIT | Keep notice |
| YT-Spam-Lists | ThioJoe - https://github.com/ThioJoe/YT-Spam-Lists | MIT | Keep notice |
| hosts (developerdan) | lightswitch05 - https://github.com/lightswitch05/hosts | Apache-2.0 | Keep notice + NOTICE |
| firstparty/multiparty trackers | Geoffrey Frogeye - https://hostfiles.frogeye.fr | MIT | Keep notice |
| phishing-filter, urlhaus-filter-agh | malware-filter - https://gitlab.com/malware-filter | MIT | Keep notice |
| suspiciousDomains | malwareworld.com - https://malwareworld.com | MIT | Keep notice |
| adfilt (Anti-Malware lists) | DandelionSprout - https://github.com/DandelionSprout/adfilt | "Dandelicence" (custom permissive) | Keep notice; honor takedown requests |

## Copyleft (preserve license + attribution)

| Source | Upstream (owner / URL) | License | Attribution |
|---|---|---|---|
| uAssets (badware) | uBlockOrigin - https://github.com/uBlockOrigin/uAssets | GPL-3.0 | Credit + GPL-3.0 + source |
| dns-blocklists | hagezi - https://github.com/hagezi/dns-blocklists | GPL-3.0 | Credit + GPL-3.0 + source |
| phishfort-lists | phishfort - https://github.com/phishfort/phishfort-lists | GPL-3.0 | Credit + GPL-3.0 + source |
| Scam-Blocklist | jarelllama - https://github.com/jarelllama/Scam-Blocklist | GPL-3.0 | Credit + GPL-3.0 + source |
| oisd | oisd - https://oisd.nl | GPL-3.0 | Credit + GPL-3.0 + source |
| notrack-blocklists | quidsup - https://gitlab.com/quidsup/notrack-blocklists | GPL-3.0 | Credit + GPL-3.0 + source |
| AdGuard DNS filter | AdGuard Team - https://github.com/AdguardTeam/AdGuardSDNSFilter (via firebog) | GPL-3.0 | Credit + GPL-3.0 + source |
| 1Hosts | badmojr - https://github.com/badmojr/1Hosts | MPL-2.0 | Credit + MPL-2.0 + source |

## Share-alike (attribution + share-alike)

| Source | Upstream (owner / URL) | License | Attribution |
|---|---|---|---|
| KADhosts | PolishFiltersTeam - https://gitlab.com/PolishFiltersTeam/KADhosts | CC BY-SA 4.0 | Credit + same license |
| KADhosts (mirror) | azet12 - https://github.com/azet12/KADhosts | CC BY-SA 4.0 | Credit + same license |
| Prigent lists (Ads / Crypto / Malware) | Université Toulouse 1 Capitole (UT1, F. Prigent) - https://dsi.ut-capitole.fr/blacklists/ (via firebog) | CC BY-SA 4.0 | Credit + same license |
| EasyList | EasyList - https://easylist.to (via firebog) | GPLv3 + CC BY-SA 3.0 | Credit + same license |
| EasyPrivacy | EasyList - https://easylist.to (via firebog) | GPLv3 + CC BY-SA 3.0 | Credit + same license |

## Public domain (free to use)

| Source | Upstream (owner / URL) | License | Attribution |
|---|---|---|---|
| referrer-spam-blacklist | Matomo - https://github.com/matomo-org/referrer-spam-blacklist | CC0 1.0 | Not required |
| BlockLists (Ads / Malware / Scam / Tracking) | ShadowWhisperer - https://github.com/ShadowWhisperer/BlockLists | Unlicense | Not required |
| blackbook | stamparm - https://github.com/stamparm/blackbook | Public domain | Not required |
| phishunt feed | phishunt - https://phishunt.io | CC0 | Not required |

## Keep + attribute (no standard OSS license)

| Source | Upstream (owner / URL) | License | Attribution |
|---|---|---|---|
| cert.pl warning list | NASK / CERT Polska - https://hole.cert.pl | No formal license (public warning list) | Credit; use as published |
| yoyo.org adservers | Peter Lowe - https://pgl.yoyo.org/adservers/ | Redistribution permitted (by written permission) | Credit |

## First-party content

| Source | Owner / URL | License | Attribution |
|---|---|---|---|
| custom/streaming.txt | fabriziosalmi/blacklists - https://github.com/fabriziosalmi/blacklists | GPL-3.0 (this repo) | Credit |

---

## Notes on mirrors

Some lists are fetched through **firebog** (`https://v.firebog.net`), which is a
mirror/index, not the original author. The rows above attribute those lists to
their **upstream** authors (AdGuard, EasyList, UT1 Toulouse), which is where the
license and credit are owed.

## Removed for licensing or availability

The following feeds were removed from `blacklists.fqdn.urls` because their terms
are incompatible with GPL redistribution, or because the source is gone:

- **StopForumSpam** `toxic_domains_whole` - CC BY-NC-ND (no distribution of derivatives).
- **red.flag.domains** - CC BY-NC-SA (non-commercial).
- **phishing.army** `extended` - CC BY-NC (non-commercial).
- **RPiList/specials** (Phishing-Angriffe / easylist / malware, incl. the two
  firebog `RPiList-*` mirrors) - CC BY-NC (non-commercial).
- **xRuffKez/NRD** `nrd-phishing-30day` - repository removed, raw URL returns 404.

The direct **urlhaus.abuse.ch** hostfile was replaced by the MIT-licensed
`urlhaus-filter-agh` repackage from **malware-filter** (same data, permissive
terms).
