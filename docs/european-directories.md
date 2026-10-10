# European bank directories

Source review date: 8 October 2026. This implementation has not been deployed to
the public service. Germany retains its existing importer and automatic updater.
Nine additional adapters are included. The Greek original workbook was verified
on 10 October 2026 through a browser download (25 mappings). Direct automated
downloads still encounter HTTP 403. See [Greek source review](greece-source-review.md)
for the observed schema, metadata formulas and usage conditions.

## Sources, formats and identifiers

Positions are one-based and refer to the normalized IBAN.

| Country | Official source | Import format | IBAN identifier | Updates / original-source verification |
|---|---|---|---|---|
| CH | [SIX Swiss Bank Master v3](https://www.six-group.com/de/products-services/banking-services/interbank-clearing/online-services/download-bank-master.html) | UTF-8 CSV, semicolon | 5–9, five-digit IID/QR-IID | Daily; 1,164 records on 8 October 2026, including 26 concatenated IIDs |
| PL | [NBP EWIB 2.0](https://ewib.nbp.pl/faces/pages/faq.xhtml) | JSON, `listaWlascicieli` | 5–12, eight-digit clearing code | On changes; complete API response with 3,141 clearing codes verified |
| LT | [Bank of Lithuania](https://www.lb.lt/en/iban-and-financial-institution-codes) | English CSV export, Windows-1257, semicolon | 5–9, five-digit National ID | On changes; export dated 5 May 2026 with 229 records verified |
| BE | [National Bank of Belgium](https://www.nbb.be/en/payments-and-securities/bank-identification-codes) | Complete XLSX list | 5–7, three-digit code | On changes; version 1 September 2026, 782 assigned codes, 218 free/unavailable codes excluded |
| CZ | [Czech National Bank](https://www.cnb.cz/cs/platebni-styk/ucty-kody-bank/) | UTF-8 CSV with BOM, semicolon | 5–8, four-digit payment system code | On changes; list valid from 1 October 2026, 47 records verified |
| LV | [Latvijas Banka](https://www.bank.lv/en/operational-areas/payment-systems/identification-of-bic-by-iban) | Linked English XLS file | 5–8, four letters | On changes; 20 records verified |
| SI | [Banka Slovenije](https://www.bsi.si/sl/placilni-sistemi/placilni-in-transakcijski-racun) | UTF-8 HTML table | Exact 5–9, otherwise 5–6 as bank prefix | On changes; 18 identifiers verified, including `rowspan` and missing BIC |
| GR | [Bank of Greece SEPA](https://www.bankofgreece.gr/en/main-tasks/payment-systems-and-settlements/sepa) | Linked XLSX file | 5–7, three-digit Bank Identifier | 25 mappings verified on 10 October 2026; direct download HTTP 403, browser works |

IBAN lengths and BBAN formats follow the
[SWIFT IBAN Registry](https://www.swift.com/swift-resource/9606/download?language=en).
Validation covers format and MOD-97, excluding domestic account checksum
algorithms. Greek account components may be alphanumeric, as may Swiss and
Latvian components. The CH adapter does not automatically support Liechtenstein.

### Source processing

- **CH:** The CSV contains 21 data fields and an additional timestamp in the
  header. IIDs are padded to five digits with leading zeros. Type 4 is a QR-IID
  in the range 30000–31999; its own mapping is retained. Concatenated identifiers
  (`Concatenation=Y`) are deleted and retain the successor identifier as a hint.
  IBANs are never rewritten to successor codes. `Valid on` must be identical
  across rows and must not follow the import validity start date.
- **PL:** Complete download from
  `https://ewib.nbp.pl/api/v1/zapytanie1/?format=json`, without account/IBAN input.
  Head offices and organizational units are processed with their clearing codes.
  The general `BIC` is used; `BIC SEPA`, TARGET and SORBNET BICs are not substituted.
  Missing BICs remain `null`.
- **LT:** The English export contains bank and branch identifiers. Bank names,
  BICs, cities and postal codes are retained. A final entirely empty padded row
  is allowed; internal gaps or unknown columns fail validation.
- **BE:** Leading zeros are preserved; separate BIC components are joined.
  `VRIJ` and `Onbeschikbaar` are not banks. Observed BIC placeholders `N/A`,
  `NAV`, `nav`, `NYA` and `-` indicate a missing BIC. English names are preferred,
  followed by Dutch, French and German.
- **LV:** The XLS file provides complete BICs. The HTML page splits BICs across
  cells and is deliberately not used as the data format. `X` at BIC position
  eight and `XXX` as a branch code are valid components, not placeholders.
- **SI:** Two-digit and five-digit identifiers remain distinct. Lookup first
  uses the exact five-digit identifier, then the two-digit bank prefix. This
  distinguishes payment institutions with their own five-digit identifiers.
  Merged name/address cells are resolved through `rowspan`.
- **GR:** The observed four-column workbook is parsed strictly, including its
  title and footer. Only the publisher's exact row-number formulas in column A
  and `=NOW()` in D2 are permitted; none are evaluated. Mapping fields cannot
  contain formulas. Three-digit identifiers retain leading zeros. The dynamic
  date is not treated as a publication date. See [source review](greece-source-review.md).

## Terms of use and approval status

The MIT-licensed code grants no rights to source data. Original directories are
neither copied into the repository nor relicensed. Tests contain synthetic
names/identifiers, including a synthetic XLS file. Bank lookup runs locally;
submitted IBANs are never transmitted to a data source. Every API response with
a dataset identifies its publisher and source URL.

| Country | Reviewed basis | Consequence / outstanding question |
|---|---|---|
| CH | [Specific Swiss Bank Master v3 record description, p. 1](https://www.six-group.com/dam/download/banking-services/interbank-clearing/bc-bank-master/bankmaster-v3.0-record-description-en.pdf) permits free use of the information; it identifies SWIFT ownership of BICs and disclaims liability. [General SIX website terms](https://www.six-group.com/en/services/legal/terms-and-conditions/terms-of-use.html) are narrower. | The specific download rule is the working basis; cite the source and claim no additional rights. |
| PL | [EWIB FAQ](https://ewib.nbp.pl/faces/pages/faq.xhtml) documents a public API without authentication and complete-list queries. | This confirms technical access, not an explicit redistribution license. Clarify and document applicable usage rights before public activation. |
| LT | [Terms of use](https://www.lb.lt/en/terms-of-use) require source attribution and author attribution where applicable. | Attribute Bank of Lithuania; do not claim a separate open-data license. |
| BE | [Copyright and use of information](https://www.nbb.be/en/disclaimer-and-legal-information/copyright-and-use-information) permits use, distribution and reproduction subject to integrity, accuracy and attribution. | Paid redistribution requires notice that the information is freely available from NBB; observe any content-specific terms. |
| CZ | [CNB website terms](https://www.cnb.cz/en/privacy-statement-and-disclaimer/disclaimer-copyright/) permit storage, distribution and reproduction of its own information with attribution; information must not be distorted. | Technical normalization with unchanged information; no editorial corrections. |
| LV | [Use of data](https://www.bank.lv/en/statistics/information-for-data-users/use-of-data) permits statistical reuse with attribution and unchanged data, with a free-availability notice where applicable. | This rule covers statistics. Its applicability to the payment directory is unconfirmed; clarify before public activation. |
| SI | [Terms of use](https://www.bsi.si/sl/pogoji-uporabe) permit storage, reproduction and distribution with attribution and unchanged data; special rules apply to advertising and paid content. | Non-commercial service with attribution; commercial/advertising use requires separate review. |
| GR | [Terms of use](https://www.bankofgreece.gr/en/useful-links/terms-of-use) permit accurate reproduction with Bank of Greece attribution; sale and/or modification require prior written consent. | Schema verified. Keep names, codes and BICs accurate, cite the publisher; resolve permission for sale or modifications before those uses. No CC-BY license is inferred. |

This is a documented technical source review, not legal approval.
`activate-directory` requires a recorded review note. For PL, LV and GR, that
review must specifically address applicable usage conditions. The original Greek
directory has now been verified; its terms and freshness still require review
for the intended public use. A successful
parser run or an arbitrary review note does not establish a license.

## Maintainer workflow

Before first starting this version, back up the database, then run
`openiban init-db`. The additional tables `directory_versions`, `directory_banks`,
`directory_active` and `directory_activations` are created. Existing German
tables/pointers are retained. This is not a general migration system;
PostgreSQL remains unapproved without integration tests.

```bash
openiban init-db
openiban fetch-directory CZ data/cz.csv
openiban import-directory CZ data/cz.csv \
  --source-url https://www.cnb.cz/cs/platebni-styk/.galleries/ucty_kody_bank/download/kody_bank_CR.csv \
  --valid-from 2026-10-01 --valid-until 2026-11-01
openiban directory-versions CZ
```

The dates in this example are a maintainer-selected review interval, not a
publisher-guaranteed lifetime. Before every import, **determine the source date
and an appropriate freshness end date**. SIX `Valid on` and NBB `Version` are also
checked against the start date; other sources require maintainer-supplied dates.

LT and LV: `fetch-directory` discovers the current English download link on the
official page. Ambiguous or missing links are not guessed. `--source-url` can
specify a manually verified current link. The LT download page returns HTTP 403
in this environment, while the explicit current CSV link works. LV link discovery
was successfully verified live. WAF/HTTP errors may require a manual browser
download. Offline imports require the actual official `--source-url`; domain
validation does not prove the local file's origin. SHA-256 identifies repeated
files; it is not a signature.

Download validates the native format and does not overwrite existing files.
Redirects stay on configured official HTTPS hosts. Downloads have a 30-second
socket timeout and a 20 MiB size limit. XLSX decompression is limited to 100 MiB;
XML entities, mapping formulas and error cells are rejected; only the exact
Greek presentation formulas documented above are allowed without evaluation. Known table structures,
identifier formats, BIC syntax and identifier uniqueness are checked. Parsing
failure writes no version and activates nothing.

Compare import output (`added`, `removed`, `changed`, `ignored_rows`,
`comparison_version`) with the previous and official complete datasets.
Investigate large decreases, incorrect source dates and unexpected changes
before activation. These countries have **no automatic activation and no new
systemd timers**.

After data review, testing and clarification of usage terms:

```bash
openiban activate-directory CZ REPLACE-WITH-VERSION \
  --review-note 'Original source date, record count, samples and CNB terms of use reviewed'
```

Activation is transactional per country and logged with the review note.
Rollback uses the same command with an earlier version. Expired versions require
`--allow-expired`; lookup then returns `stale` without bank data. Future versions
cannot be activated before their validity start date. Identical files are
idempotent per country; conflicting periods/source URLs are rejected.
German automatic updates remain unchanged.

## API and operations

`GET /v1/countries` lists the ten supported IBAN formats. The field
`bank_lookup_supported` indicates an available lookup implementation, not
currently imported bank data or final source approval. Without an activated
current country version, lookup reports `unavailable` or `stale`.
`/health/ready` remains a German readiness indicator; it does not confirm all
countries. An unknown bank code is independent of an invalid IBAN checksum.
`postal_code`/`city` remain empty when the source does not provide separate fields.

Tests: `ruff check .`, `ruff format --check .`, `pytest -q` with the updated
`requirements-dev.lock`. All regular tests run offline. Coverage includes native
formats, leading zeros, Polish units, Slovenian identifiers/rowspans, missing
BICs, reserved codes, Swiss concatenation/QR-IIDs, damaged files, size limits,
provenance, schema extension, country isolation, CLI, activation, rollback,
MOD-97 and API lookup. Greek offline fixtures reproduce the observed schema
with synthetic data; separate live verification parsed the original workbook.

The seven reachable original sources were downloaded separately on 8 October
2026 and processed by the adapters. Original files reside outside the repository.
Live verification is deliberately separate from CI: sources/WAFs must not affect
the offline suite. GR was verified separately on 10 October 2026. Usage conditions
and the remaining questions above must be reviewed before public activation.


## Netherlands: provisional industry source

Added on 10 October 2026. Betaalvereniging Nederland is an industry association,
not a central-bank source. The user-selected [BIC list workbook](https://www.betaalvereniging.nl/wp-content/uploads/2025/11/BIC-lijst-NL.xlsx)
was retrieved and parsed successfully: 96 identifiers, dated 2 September 2026
inside the workbook. The URL directory date is not the publication date.
The [publisher's IBAN/BIC page](https://www.betaalvereniging.nl/kennisbank/iban-en-bic/)
provides context. Original data is not bundled in this repository.

NL IBANs have 18 characters: a four-letter identifier at positions 5–8 followed
by ten account digits. Validation checks country format and MOD-97, not account
existence. The XLSX adapter requires the observed bilingual title, publication
date and three-column header. It preserves provider names and BICs, verifies
identifier/BIC agreement and country NL, and rejects duplicates, missing cells,
formulas and unexpected schemas. Existing size and XML protections apply.
The source publication date must not follow the import validity start date.
No automatic activation is added. Missing codes are lookup misses, not proof
that an account does not exist or that the source covers every provider.

The [website disclaimer](https://www.betaalvereniging.nl/disclaimer/) grants
limited personal non-commercial access and restricts copying, adaptation,
publication and distribution without prior written permission, subject to legal
exceptions. Public availability does not establish permission for public API
redistribution. No file-specific redistribution permission has been established.
Clarify and document applicable permission before public activation; retain the
provisional source attribution. Technical import tests do not resolve usage rights.

```bash
openiban fetch-directory NL data/nl.xlsx
openiban import-directory NL data/nl.xlsx \
  --source-url https://www.betaalvereniging.nl/wp-content/uploads/2025/11/BIC-lijst-NL.xlsx \
  --valid-from 2026-10-10 --valid-until 2026-11-10
openiban directory-versions NL
```

The validity interval above is a maintainer-selected example. Review freshness,
record counts, changes and usage permission before any activation. Use
`activate-directory NL VERSION --review-note 'Documented review and permission'`
only after that review. This implementation does not deploy or activate NL.
