# Security Policy

## Reporting a vulnerability

**Please do not open a public issue or pull request for a security problem.**

This project publishes DNS filtering data that people install on machines you
cannot see. A vulnerability disclosed in public is a vulnerability available to
everyone who reads the repository before it is fixed.

Report it privately through **GitHub Security Advisories**:
[report a vulnerability](https://github.com/fabriziosalmi/blacklists/security/advisories/new).

This creates a private thread visible only to you and the maintainers, and it
can be turned into a published advisory once a fix is out.

Please include what you found, how to reproduce it, and what an attacker could
do with it. You will get an acknowledgement within 7 days, and an assessment
within 30. Fixes are published as a normal release; you will be credited unless
you ask not to be.

## What counts as a vulnerability here

This is a data pipeline, so the interesting attacks are on what it publishes
rather than on a running service:

- a way to get an arbitrary domain into the published list
- a way to make the build fetch or execute something it should not
- a way to tamper with a published artifact, or with the SHA-256 that describes it
- credential or token exposure in the workflows

## What is not a vulnerability

**A wrongly blocked domain is not a security issue** — it is a false positive,
and it is entirely normal for a list aggregated from third parties. Report it as
a regular issue and it will be whitelisted:
[open an issue](https://github.com/fabriziosalmi/blacklists/issues/new/choose).

The same goes for a domain you think is missing, and for anything about the
upstream lists themselves, which are maintained by other people
(see [SOURCES.md](SOURCES.md)).

## Verifying what you downloaded

Every build publishes the SHA-256 of `blacklist.txt` on the
[statistics page](https://fabriziosalmi.github.io/blacklists/#stats), alongside a
link to the workflow run that produced it. Checking the file you received
against that digest is the supported way to confirm you have the artifact this
project published.
