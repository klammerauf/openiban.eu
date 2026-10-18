# Dutch BIC list and recurring import

Verified 18 October 2026. Publisher and required attribution: **Betaalvereniging Nederland**.
The maintainer supplied written permission to use the list free of charge without
formal licence agreement, conditional on attribution and the disclaimer below.
This permission does not relicense the source data under the repository's MIT licence.

Source: https://www.betaalvereniging.nl/en/knowledge-base/iban-and-bic/bic-code/
Observed attachment: https://www.betaalvereniging.nl/wp-content/uploads/2025/11/BIC-lijst-NL.xlsx
Observed workbook: 96 mappings, publication date 2 September 2026, one worksheet,
three columns (BIC, Identifier, payment service provider). Existing strict parser
verified against the downloaded original; original data is not bundled.

Required notice, included in each NL API dataset response:

> Source: Betaalvereniging Nederland. Dutch BICs and bank codes may be changed,
> revoked or added at any time. The list is carefully maintained, but no guarantee
> of accuracy is provided. Inclusion is voluntary and the list may be incomplete.

The publisher announces changes via
https://www.betaalvereniging.nl/en/news/category/iban-bic-list/feed/ .
The workbook carries the last-update date; the URL contains an upload directory,
not a version date. Daily full polling discovers exactly one official HTTPS
BIC-lijst-NL.xlsx link on the source page and compares SHA-256, independent of RSS
availability. RSS is informational; no feed subscription or feed parser is installed.
Downloads and redirects are host restricted, time and size bounded; spreadsheet
formulas, malformed schema, duplicate identifiers and invalid mappings fail closed.
No BIC is constructed from an IBAN. Missing entries are inconclusive, not proof of
an invalid bank code (the API returns null bank_code_valid for absent NL entries).

`openiban update-nl` uses the existing country version/staging tables, plus an
additive directory_checks table. It stores immutable SHA-256, source URL, import
time, source date (valid_from), row counts and activation history. API metadata
adds published_on, checked_at and disclaimer. valid_until=9999-12-31 is a storage
sentinel: the publisher supplies no expiry. Actual freshness expires after seven
calendar days without a successful check; identical files refresh checked_at
without a new version or activation. This is an operational policy, not a source
accuracy guarantee. Manual activations without a matching successful check are stale.

A local advisory lock prevents overlapping scheduled NL runs. Activation and
freshness updates share a database transaction and compare the previous country
version under a write lock. Only NL rows change. Acceptable snapshots have 50–1000
entries; more than 10% added/removed/changed identifiers versus the active snapshot,
future source dates and backward source dates require manual review. Rejected
runs exit nonzero and retain the active dataset and its last successful check.
A reviewed large change can be staged/activated with the existing directory CLI;
the next successful update validates and marks that version fresh. A publisher
URL change for byte-identical data is conservatively rejected by existing provenance
rules and needs maintainer review. Historical versions allow manual rollback;
a subsequent updater will reapply the official snapshot unless its timer is stopped.

## Server installation (not performed by this change)

This PR builds on feat/spain-entity-directory, which includes the European directory
architecture. Merge/deploy that dependency before this change. Back up the database
and install this release and its locked dependencies into /opt/openiban.eu/.venv.
Use the production database URL for every command; the supplied units assume SQLite.
Run `openiban init-db` as the service user to create additive tables, then restart
the API so the response model includes the notice. Run `openiban update-nl` as that
same user with write access to /var/lib/openiban (including nl-updates). Inspect
its JSON output and an NL /v1/validate response before enabling the timer.

Install deployment/netherlands/openiban-nl-update.{service,timer} into
/etc/systemd/system/, run `systemctl daemon-reload`, then
`systemctl enable --now openiban-nl-update.timer`.
It checks daily at 05:40 Europe/Berlin plus up to 30 minutes jitter and catches up
a missed run. Inspect `journalctl -u openiban-nl-update.service` and
`systemctl list-timers openiban-nl-update.timer`. Configure existing monitoring to
alert on failed units; no email integration is added. DE timers and the manual ES
importer are unchanged. Stop/disable this NL timer before manual rollback/recovery.
No production credentials, server changes or production import were performed.
