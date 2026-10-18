# Spain: reviewed TARGET BIC supplement

Checked 18 October 2026. No production database changed and no deployment performed.
This supplements the ES importer on `feat/spain-entity-directory`.

## Sources and freshness

The current [official TARGET landing page](https://www.bde.es/wbe/es/punto-informacion/contenidos/sistemas-pago-infraestructuras/target-banco-espana/)
links the requested [BIC-sorted PDF](https://www.bde.es/f/webbe/Comunes/sispago/menu_dcha/TARGET_BE_BIC.pdf).
HTTP 200, no replacement URL needed. Downloaded 2026-10-18; 70,383 bytes;
SHA-256 `bd1fcc098051f09a59e478a549f30811269684e7fcca919a6b62322740f14643`.
HTTP Last-Modified: 2026-04-07 15:07:49 UTC; internal PDF modification time:
2026-04-07 12:56:01 UTC. Neither is an explicit effective date. The table has no
printed publication or expiry date; do not describe it as effective October 2026.
It is the currently linked file, with limited evidence of business freshness.

The [official MFI CSV](https://www.bde.es/webbe/es/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-es.csv)
was downloaded again. Its 243,865 bytes and SHA-256
`0c4b89814b4a33cf68f6577ad32a03472a50b806c7cd2ab6339ca23c818648c7`
match the previous conversation attachment documented in `spain-source-review.md`.
The MFI page reports 8 October 2026; the CSV has no effective date.

Both TARGET pages were visually checked against extracted rows. Also compare
[NRBE order](https://www.bde.es/f/webbe/Comunes/sispago/menu_dcha/TARGET_BE_NRBE.pdf)
and [name order](https://www.bde.es/f/webbe/Comunes/sispago/menu_dcha/TARGET_BE_Denominacion.pdf).
Search-engine text extraction incorrectly showed `CDNESBBXXX` for 3025; the three
actual downloaded PDFs agree on `CDENESBBXXX`. Never repair a BIC from search snippets.

## Reconciliation

Join only exact four-digit NRBE to `CÓDIGO DE SUPERVISOR`, preserving leading zeros.
Keep MFI names in the directory. Names are checked after case, accent, punctuation
and spacing normalization; no fuzzy matching, bank-code derivation or BIC8 expansion.
All ten remaining published-name differences were individually reviewed and bound
to the exact code, both names and BIC. Reasons are included in the mapping and bundle.
They are legal-form/branch abbreviations, a bilingual name or an omitted legal form;
there are no unresolved institution identity conflicts in this snapshot.

| Result | Count |
| --- | ---: |
| MFI source rows | 242 |
| MFI credit institutions (coverage denominator) | 184 |
| MFI rows excluded by existing category policy | 58 |
| TARGET participant rows | 50 |
| TARGET published BIC11 | 47 |
| TARGET participants matching MFI credit institutions | 43 |
| Credit institutions with usable BIC11 | 40 (21.74%) |
| Normalized name matches with BIC11 | 30 |
| Individually reviewed name variants with BIC11 | 10 |
| BIC withheld (`*`) | 3 |
| MFI credit institutions absent from TARGET | 141 |
| TARGET participants outside MFI credit-institution scope | 7 |
| Duplicate NRBE / published BIC11 / malformed BIC11 | 0 / 0 / 0 |

Unpublished BICs: 1474 (Citibank Europe), 1491 (Triodos), 3001 (Caja Rural de
Almendralejo). The PDF footnote says these participants requested nonpublication.
Leave them null; do not infer or fill them from memory.

Outside scope: 3669, 3682, 3760, 7415, 9020, 9094, 9096. These do not expand the
existing conservative credit-institution directory. The 141 missing institutions
are listed individually in the CSV, not treated as closed or invalid banks.
Distinct branch BICs such as CECAESMM045, CECAESMM056 and CAGLESMMVIG are preserved.
TARGET RTGS account-holder BICs are evidence of institution identifiers, not proof
of routing suitability for every retail account or of account existence.

## Reproduce and stage safely

Publisher files and resulting mapping/bundle are review artifacts, outside Git.
Retain original PDFs, original MFI CSV, review.json, mapping CSV and bundle together.
A bundle is a trusted, reviewed intermediate artifact, not a publisher signature.
Its PDF hash identifies the retained original; runtime staging validates the text
hash and schema, but does not re-extract the PDF to verify the text/PDF relationship.
Rebuild from the originals before accepting a bundle from another party.

Preparation is offline, uses Poppler `pdftotext -layout` (30-second timeout) and
never opens a database or downloads anything:

```bash
python -m openiban.spain_target lista-mfi-es.csv TARGET_BE_BIC.pdf NEW_OUTPUT_DIR \
  --review review.json
```

`review.json` contains `provenance` (retrieved_on and separately labeled dates),
`name_reviews` and `blocked` arrays. Every decision contains `nrbe`, `target_name`,
`mfi_name`, `bic11` and a nonempty `reason`; it applies only to those exact rows.
Unreviewed name differences and blocked source conflicts retain null BICs.
Unknown/truncated table structures, malformed BIC11, duplicate codes/BIC11,
corrupt provenance and mismatched reviews fail closed. Original MFI CSV imports
still work and leave all BICs null.

The tool writes `es-target-bundle.json`, `es-bic-mapping.csv` and `summary.json`.
The bundle embeds the exact original UTF-8 MFI text, extracted TARGET text, URLs,
source hashes, dates and explicit review decisions. The mapping is the full outer
join (191 rows), including missing/withheld/out-of-scope cases, page references,
source and accepted BICs, both names and per-row provenance. Import only the JSON
bundle; the CSV is for audit and must be read with NRBE as text.

Use the existing staging command with an explicitly selected **test database**:

```bash
OPENIBAN_DATABASE_URL=sqlite:////tmp/openiban-es-target-review.db openiban init-db
OPENIBAN_DATABASE_URL=sqlite:////tmp/openiban-es-target-review.db \
  openiban import-directory ES NEW_OUTPUT_DIR/es-target-bundle.json \
  --valid-from 2026-10-18 --valid-until 2026-11-17 \
  --source-url https://www.bde.es/f/webbe/Comunes/sispago/menu_dcha/TARGET_BE_BIC.pdf
```

These dates are an example operator review window, not publisher validity dates.
Staging never activates. No new schema, timer, automatic activation or deployment
is introduced. The immutable version digest covers the entire bundle, including
both sources and review decisions; an updated BIC supplement creates a new version.
The existing API source_url points to TARGET for bundles, and sha256 identifies
the complete archived bundle. The second source and detailed dates are in that
bundle and audit CSV, not new API fields. Activation/rollback remain explicit
existing operations, described in `spain-source-review.md`.
