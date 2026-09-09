---
name: Whitelist request (a domain is wrongly blocked)
about: Report a domain this list blocks that it should not
title: 'Whitelist: '
labels: whitelist
assignees: ''

---

<!--
This is the right place for a false positive. It is not a security issue and it
is not a bug in the tooling - domains arrive from third-party lists, and one of
them occasionally blocks something it should not.

Check first: https://fabriziosalmi.github.io/blacklists/  (the search box tells
you whether a domain is listed, and which source supplied it)
-->

### Domain(s)

<!-- One per line, no http:// and no path. -->

```

```

### Why it should not be blocked

<!-- What breaks when it is blocked, and what the domain is actually for.
     "It is my site" is a fine answer. So is "this is the CDN for X". -->


### What stops working

<!-- e.g. "Windows Update fails", "logging into example.com hangs",
     "every page on my site loses its images". -->


### Which resolver or client are you using?

<!-- Pi-hole / AdGuard Home / Unbound / BIND RPZ / uBlock Origin / other.
     This matters: the Unbound and RPZ formats block subdomains too, so a
     blocked apex has a much wider effect there than in Pi-hole. -->


### Anything else

<!-- If the site search named the source that supplied the domain, paste it
     here - it usually points straight at where the fix belongs. -->
