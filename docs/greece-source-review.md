# Greece source review

Verified on 10 October 2026. No production dataset was activated or deployed.

## Bank of Greece: primary BIC mapping

- Publisher page: https://www.bankofgreece.gr/en/main-tasks/payment-systems-and-settlements/sepa
- Linked download: https://www.bankofgreece.gr/RelatedDocuments/en-BIC-from-IBAN.xlsx
- Format: XLSX (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
- Retrieved via the page's browser download; direct requests returned an HTML
  Access Denied page. An HTTP download success alone is not evidence of XLSX.
- Retrieved size: 35,474 bytes.
- SHA-256: `8647b6dc98ad1d3a324ccf90fb5f7b8b259e0bd8699fd253a65f1b1f92cd7bb2`.
- One worksheet: `BIC-from-IBAN`; four columns; 25 PSP mappings.

Observed structure:

| Row / column | Content | Handling |
|---|---|---|
| B1 | `BIC-from-IBAN derivation table` | Required title |
| C2 / D2 | `updated on:` / `=NOW()` | Dynamic metadata; never evaluate or infer publication date |
| Row 3 | Empty | Required separation |
| A4 | `#` | Presentation row number |
| B4 | `Payment Service Provider (PSP)` | Bank/provider name |
| C4 | `PSP identifiers used in IBAN (positions 5-7)` | Three-digit bank identifier |
| D4 | `BIC` | BIC8 or BIC11 syntax; country must be GR |
| A5 onwards | `=ROW(A1)` etc., or literal integer | Exact sequential numbering only |
| After data | Empty row, then `Note:` / `Only PSP with BIC codes are included` | Required footer |

The source mixes string identifiers such as `010` and numeric identifiers such
as `701`; normalize to three-digit strings. Preserve provider names and BICs,
without inventing branch codes or adding `XXX`. Empty address fields remain
empty. The source explicitly limits coverage to PSPs with BICs, so absence is
not proof of account invalidity or complete market coverage.

The original was also staged and activated only in a disposable local SQLite
database: all 25 stored names/BICs matched, initial staging did not activate,
and reimport was idempotent.

Live checks included `010 → BNGRGRAA`, `011 → ETHNGRAA`, `014 → CRBAGRAA`,
`017 → PIRBGRAA`, and `026 → ERBKGRAA`. Parsing checks all 25 records for schema,
required fields, uniqueness and syntax. The workbook provides no dependable
publication date: its NOW formula changes on recalculation. Retrieval date is
not the publisher's last update date. Freshness intervals remain a maintainer
choice and require review.

The existing country adapter, staging tables, CLI, activation review note,
provenance and rollback are reused. Formula exceptions apply only to GR and only
to the observed presentation cells; all mapping formulas and error cells fail.
Original publisher files are not committed; CI fixtures are synthetic.

## HBA HEBIC: optional cross-check, not a BIC source

Publisher page: https://www.hba.gr/Info/hebicmap

The page currently labels the export **2026, second quarter**. This is a
retrieved current listing, not evidence of a guaranteed quarterly update SLA.

| Export | Download URL | Observed records |
|---|---|---|
| Banks CSV | https://www.hba.gr/info/hebicmap/downloadbanks | 35 |
| Branches CSV | https://www.hba.gr/info/hebicmap/downloadbranches | 4,974 service points |

Both endpoints downloaded successfully without authentication. The response
reported `application/octet-stream`. Files decode as Windows-1253, use CRLF
lines and semicolon separators, and begin with a Greek title row followed by
headers. Data rows have an extra empty trailing field. Identifiers are enclosed
in literal apostrophes (`'011'`, `'0561001'`), which must be stripped without
losing leading zeros. No BIC column exists in either export.

Bank headers: `Κωδικός Αριθμός`, `Όνομα Πιστωτικού Ιδρύματος`, `Διεύθυνση`,
`Τηλέφωνο`, `Fax`, `URL` (code, institution name, address, phone, fax, URL).

Branch headers: `Κωδικός HEBIC`, `Τράπεζα`, `Ονομασία Καταστήματος`,
`Διεύθυνση`, `Ταχυδρομικός Κώδικας`, `Τηλέφωνο`, `Fax`, `Δήμος`, `Νομός`,
`Τραπεζικό Κατάστημα`, `ΑΤΜ`, `APS` (HEBIC, bank, service point name, address,
postal code, phone, fax, municipality, prefecture, branch/ATM/APS flags).

HEBIC comprises the three-digit bank code and four-digit branch code. The
branches export also includes ATM/APS points, so its row count is not a count of
bank branches. Of 4,974 rows, 3,390 do not carry a seven-digit numeric HEBIC
(after removing apostrophes); examples include `SNB00049` and empty values.
Only validated seven-digit numeric HEBICs can be split into bank/branch codes.
The institution export overlaps 18 of the 25 BoG codes; the seven BoG-only
codes are `605`, `610`, `701`, `702`, `703`, `705`, `732`. This reflects different
coverage and is not automatically a data error. HBA has broader/different coverage than the BoG PSP-with-BIC
list. Do not merge names or infer BICs from HBA automatically. An optional
cross-check can join bank code to BoG C-column; discrepancies need manual review.
No additional HBA importer is needed for bankcode-to-BIC resolution.

## Usage conditions

Bank of Greece terms:
https://www.bankofgreece.gr/en/useful-links/terms-of-use

The terms permit use if information is reproduced accurately and the Bank of
Greece is cited as source. Sale and/or modification require prior written
consent. This is not a CC-BY grant. Technical extraction preserves information;
its classification under the modification clause for a particular public API
use has not been established. Record the intended-use review before public
activation; obtain consent where sale or modification applies. The publisher
disclaims accuracy/completeness and uninterrupted availability.

HBA terms appear in the footer of https://www.hba.gr/ and the HEBIC page.
They permit reproduction/republication with source attribution, subject to
third-party rights and any specific conditions requiring prior approval. The
HEBIC note places responsibility for content with each bank and disclaims HBA
liability. No separate open-data license is claimed.

## Maintainer workflow

Try the configured bounded downloader first:

```bash
openiban fetch-directory GR data/gr.xlsx
```

If the source denies automated access, download the linked file using a browser
and import that local original. Do not import an HTML denial page or bypass
security challenges. Example review interval (not publisher validity):

```bash
openiban import-directory GR data/gr.xlsx \
  --source-url https://www.bankofgreece.gr/RelatedDocuments/en-BIC-from-IBAN.xlsx \
  --valid-from 2026-10-10 --valid-until 2026-11-10
openiban directory-versions GR
```

Check the complete source, record count, changes, provenance, freshness and
intended-use conditions before `activate-directory GR VERSION --review-note`.
Never treat a successful parser run as automatic approval to activate.
