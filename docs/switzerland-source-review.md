# Switzerland source review

Verified on 10 October 2026 against the live SIX Swiss Bank Master v3.

## Source and download

- Publisher page: https://www.six-group.com/de/products-services/banking-services/interbank-clearing/online-services/download-bank-master.html
- CSV: https://api.six-group.com/api/epcd/bankmaster/v3/bankmaster_V3.csv
- Specification: https://www.six-group.com/dam/download/banking-services/interbank-clearing/bc-bank-master/bankmaster-v3.0-record-description-en.pdf

The publisher describes a daily-updated extract suitable for software bank
master updates. The CSV downloaded without authentication. It is UTF-8,
semicolon-separated, CRLF, with 21 data columns and a creation stamp appended
only to the header. The retrieved header stamp is `202610091630000` (15 digits,
whereas the specification describes a 14-digit timestamp). The adapter accepts
both observed and specified lengths; this stamp is not used as validity.

Retrieved size: 139,551 bytes. SHA-256:
`6fb28af947cc345018c596856f3de4c00efe6c747fdadb5f93d814b831fe0e5d`.
All 1,164 records have `Valid on = 2026-10-12`. This is a future snapshot relative
to the review date and must not be activated early. `published_on` in the shared
adapter model stores this effective date for the staging date guard; it is not
asserted to be a publication date.

## Columns and interpretation

| Columns | Handling |
|---|---|
| IID/QR-IID | Pad numeric identifier to five digits; matches CH IBAN positions 5–9 |
| Valid on | ISO date, identical across all rows; earliest permitted import validity start |
| Concatenation / New IID/QR-IID | Y denotes a no-longer-valid code; retain successor hint, no automatic IBAN rewriting |
| SIC IID / Headquarters | Validate numeric identifiers; do not substitute for the IBAN IID |
| IID type / QR-IID allocation | 1 headquarters, 2 main branch, 4 QR-IID; QR range 30000–31999 |
| Name of bank/institution | Preserve name, including publisher status prefixes |
| Street Name / Building Number | Present in source; not stored in existing API bank schema |
| Post Code / Town Name | Retained as postal code and city |
| Country | Validate uppercase two-letter syntax; international institutions are legitimate |
| BIC | Preserve supplied BIC; missing values remain null |
| SIC participation / RTGS customer payments, CHF / IP customer payments, CHF / euroSIC participation / LSV+/BDD, CHF / LSV+/BDD, EUR | Validate Y/N; not exposed as API reachability claims |

Current counts: 336 headquarters, 576 main branches, 226 QR-IIDs and 26
concatenated identifiers. There are 1,138 active records, of which 1,125 have
BICs and 13 do not. This is an identifier directory, not a count of distinct
banks. Multiple IIDs can share a BIC. QR-IIDs retain their own supplied mapping;
they are not replaced by their allocation IID. The parser rejects allocation
fields on ordinary IIDs and ordinary types in the reserved QR range.

Active institution countries include CH, LI and others. Never require BIC
country CH or filter foreign institutions out of the Swiss IID directory.
Liechtenstein IBAN validation is not enabled by this CH importer.

Examples from the original: `00100 → SNBZCHZZXXX` (Swiss National Bank),
`09000 → POFICHBEXXX` and QR-IID `30000 → POFICHBEXXX` (PostFinance).
Missing BICs remain missing; concatenated codes are reported through the
existing deleted-code behavior without returning an active bank mapping.

## Usage conditions

The specific CSV specification, page 1, expressly permits free use of the
Download Bank Master information. It identifies SWIFT ownership of BICs,
disclaims completeness and liability, and permits source changes/deletion.
This specific statement is the working reuse basis; cite SIX and the source URL,
and do not claim that the MIT code license covers publisher data or BIC rights.
General website terms are available at:
https://www.six-group.com/en/services/legal/terms-and-conditions/terms-of-use.html
Original data is not committed; test data is synthetic.

## Maintainer workflow

```bash
openiban fetch-directory CH data/ch.csv
openiban import-directory CH data/ch.csv \
  --source-url https://api.six-group.com/api/epcd/bankmaster/v3/bankmaster_V3.csv \
  --valid-from 2026-10-12 --valid-until 2026-10-19
openiban directory-versions CH
```

The end date is an example review interval, not publisher-guaranteed validity.
Inspect `Valid on` on every new download, the full source, changed/removed rows
and usage basis before activation. A future import may be staged, but activation
is rejected before its validity start. Fetching tomorrow may return a different
snapshot. No scheduled automatic activation is introduced.
