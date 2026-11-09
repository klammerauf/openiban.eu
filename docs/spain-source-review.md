# Spain: source review and controlled operation

Reviewed 12 October 2026. This change is not deployed. It builds on the versioned
European directory model in PR #1; Germany's schema, active data, updater,
readiness semantics and timers retain their existing behavior.

## Actual input and official references

The conversation attachment `lista-mfi-es.csv` is UTF-8 with BOM, comma separated,
and padded with spaces after the final field. It contains 242 rows and eight
columns, in this exact order:

| Column | Use |
|---|---|
| CÓDIGO EUROPEO | European institution identifier; not the lookup key |
| LEI | Optional legal entity identifier; not a BIC |
| NOMBRE | Institution name, retained without translation |
| CATEGORÍA | Only `Entidad de crédito` enters the bank directory |
| DIRECCIÓN | Address is not split heuristically into city/postal code |
| INFORME | Reporting indicator (`Sí`/`No`); not authorization or bank eligibility |
| ENTIDAD MATRIZ | Optional parent identifier; not a replacement bank code |
| CÓDIGO DE SUPERVISOR | Exact four-digit entity code, preserving leading zeros |

Attachment SHA-256:
`0c4b89814b4a33cf68f6577ad32a03472a50b806c7cd2ab6339ca23c818648c7`
(243,865 bytes). The official page observed on review reports 8 October 2026.
The CSV itself contains no publication date or validity interval.

- [Official list and linked CSV](https://www.bde.es/webbe/es/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-es.html)
- [Official CSV URL](https://www.bde.es/webbe/es/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-es.csv)
- [BdE explanation of Spanish IBAN components](https://clientebancario.bde.es/pcb/es/blog/que-se-esconde-tras-los-numeros-de-tu-cuenta-corriente-.html)
- [Statistics reuse conditions](https://www.bde.es/wbe/es/estadisticas/recursos/terminos/terminos-de-uso.html)
- [General website conditions](https://www.bde.es/wbe/es/pie/aviso-legal/)

The official page confirms the schema, categories and differing European and
supervisor identifiers. For example, European identifier `ES0224` has supervisor
code `0073`; some European identifiers contain a tax identifier. Do not require
these fields to agree or derive the entity code from the European identifier.

184 credit institutions are imported. 58 rows are excluded: 53 other
institutions, four money market funds and one central bank. This is a conservative
credit-institution directory, not a complete register of all payment providers
or proof of an individual institution's current account services. Categories
outside the observed vocabulary require a new source review and fail import.

There is **no BIC column**. All ES BICs remain `null`; city and postal code remain
empty. Neither LEI, parent ID nor European ID is substituted for a BIC. Public
access does not grant additional data rights: preserve accurate names, cite BdE,
disclose the filtering above and do not imply sponsorship. The reviewed terms
require integrity and attribution; paid reuse has an additional free-source
notice. Review the intended publication against the linked conditions before
activation; no separate CC license is asserted.

## Validation and API semantics

ES IBANs have 24 ASCII characters: `ES`, two check digits and 20 digits. The entity
code is at positions 5–8. Whitespace and lowercase normalize as for DE; punctuation,
non-ASCII characters, incorrect lengths and nonnumeric BBANs fail. Check digits
must be canonical (02–98), and MOD-97 must equal one. Domestic CCC check digits,
account existence, holders and balances are not checked.

`POST /v1/validate` and `GET /v1/countries` include ES. An ES IBAN with a correct
format and MOD-97 remains `iban_valid: true` even if its entity code is absent:

- No active ES dataset: `bank_lookup_status: unavailable`, `bank_code_valid: null`.
- Current dataset, retained code: `found`, `bank_code_valid: true`, `bank.bic: null`.
- Current dataset, absent or excluded code: `not_found`, `bank_code_valid: false`.
  This means absent from this filtered snapshot, not proof that the IBAN or account
  is nonexistent, or that the institution cannot provide payment services.
- Expired or not-yet-valid active dataset: `stale`, `bank_code_valid: null`, no bank.
- Invalid format/checksum: `not_checked`, `bank_code_valid: null`.

Responses include the source URL, raw-file SHA-256, version and operator validity
interval. Lookups are local; no IBAN or account is sent to Banco de España.
`/health/ready` continues to report DE readiness only.

## Migration, staging, activation and rollback

For an existing DE-only database, first create and verify a backup using the
existing procedure in [operations](operations.md), and test on a restored copy.
Serialize initialization with import/update jobs. Run `openiban init-db` explicitly
before imports. It creates the additive `directory_versions`, `directory_banks`,
`directory_active` and `directory_activations` tables if missing, and inserts a
null ES active pointer if absent. It does not alter, copy or remove DE rows or
reset any active pointer. Repeating initialization preserves all active data.
If the European tables already exist, only the missing ES pointer is needed.
This is an additive schema initialization, not a general-purpose migration system.

Use a local reviewed export, or `openiban fetch-directory ES NEW-FILE.csv` for
the configured HTTPS download. Downloads and redirects are limited to
`www.bde.es`. Download failure or schema changes leave active data untouched.
Retain the original file outside Git with provenance and its checksum.

Example on a **test database** (dates below are an operator review window, not
an expiry period published by BdE):

```bash
export OPENIBAN_DATABASE_URL=sqlite:////tmp/openiban-es-review.db
openiban init-db
openiban import-directory ES /path/to/lista-mfi-es.csv \
  --valid-from 2026-10-08 --valid-until 2026-11-07 \
  --source-url https://www.bde.es/webbe/es/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-es.csv
openiban directory-versions ES
# Review totals, added/removed/changed codes, validity, provenance and usage.
openiban activate-directory ES VERSION-ID \
  --review-note 'Reviewed BdE source, credit-institution filtering, freshness and usage'
```

The import report must show 242 total rows, 184 bank rows and 58 ignored rows for
this attachment. Parsing validates the complete file before database writes;
unknown headers, widths, codes, categories, control characters, formulas,
multiline fields, duplicate supervisor codes and empty credit-institution sets
fail closed. Limits are 20 MiB and 100,000 source rows. Import is transactional,
immutable and idempotent for identical file/validity/provenance. A conflicting
reimport is rejected. Staging does not activate. Activation requires a review
note, a version belonging to ES and a currently valid interval; changes and
previous versions are recorded transactionally.

Rollback uses `activate-directory ES PREVIOUS-VERSION --review-note 'Reason'`.
An expired rollback additionally requires `--allow-expired` and remains stale
in the API. Future versions cannot activate early. Code rollback to the original
DE release can leave the additive tables in place; do not delete them or restore
an old full database over newer DE updates. Keep the existing DE timer schedules
and configuration. There is no ES automation or automatic ES activation.

## Verification

Offline tests cover observed CSV syntax, leading zeros, category filtering,
European/supervisor mismatches, missing BICs, malformed files, duplicate codes,
format/MOD-97, separate API bank evidence, staging, rollback, expiry, future
activation, failed imports and repeatable DE-only schema migration. Existing DE
importer, API, updater and notification tests run unchanged. The real attachment
was also staged, activated and checked against every retained source row in a
disposable SQLite database; idempotent reimport and unchanged DE lookup were
verified. Original publisher data is not committed. PostgreSQL was not tested.
