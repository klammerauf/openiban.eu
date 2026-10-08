# OpenIBAN.eu

Independent, non-commercial project for IBAN validation and bank data lookup for
Germany in the initial version. The API uses
FastAPI, versioned Bundesbank data and automatic updates. No ERP dependency.

## Use the public service without installing it

Use OpenIBAN.eu directly through the hosted API. You do not need to operate a
server or import bank data yourself.

- **API base URL:** https://api.openiban.eu
- **Interactive API documentation:** https://api.openiban.eu/docs
- **Readiness and active dataset version:** https://api.openiban.eu/health/ready

The API currently requires no registration or API key. The initial public
service supports German IBANs. Example:

```bash
curl -sS https://api.openiban.eu/v1/validate \
  -H 'Content-Type: application/json' \
  -d '{"iban":"DE58 1234 5678 0123 4567 89"}'
```

This example is synthetic: a correct IBAN checksum confirms neither an existing
bank relationship nor an account. Also evaluate `bank_lookup_status` and
`bank_code_valid`.

The public service limits request rates. Handle HTTP 429 with a delay and a
limited number of retries. Send IBANs only in the JSON body, never as URL parameters.

The website with its own validation form at `openiban.eu` is still in preparation.
The API service at `api.openiban.eu` is already available. The installation steps
below are intended for development and self-hosting.

## Features

- German IBANs: remove spaces, uppercase ASCII letters,
  validate country format/length and MOD-97.
- Return bank name, BIC, BLZ, postal code and city from the active Bundesbank dataset.
- Distinguish unknown/deleted bank codes, missing data and expired data.
- Validate the public Bundesbank TXT file, import a version and explicitly activate it.
- Reactivate an earlier dataset version while retaining activation history.
- OpenAPI documentation at `/docs` and automated tests in GitHub Actions.

`iban_valid` means **correct format and IBAN checksum**. It does not confirm account
existence, account ownership, solvency or domestic account checksum algorithms.
The bank-code status is reported separately in `bank_code_valid`.
Other countries return `reason: unsupported_country` and `iban_valid: null`.
Additional country importers are being developed in [draft PR #1](https://github.com/klammerauf/openiban.eu/pull/1).

## Run locally (Python 3.12)

```bash
git clone https://github.com/klammerauf/openiban.eu.git
cd openiban.eu
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
openiban init-db
uvicorn openiban.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Windows PowerShell: use `.venv\Scripts\Activate.ps1` instead of `source`.
The default database is `data/openiban.db`, relative to the working directory.
Start the API and import commands from the same directory. `OPENIBAN_DATABASE_URL`
can specify another database location; `.env.example` shows the format.
A `.env` file is not loaded automatically.

SQLite allows local use without a database server. SQLAlchemy prepares for
PostgreSQL (`pip install -e '.[postgres]'` and an appropriate connection URL).
This initial implementation was tested with SQLite; PostgreSQL integration tests
and schema migrations will precede production use with PostgreSQL.

IBAN validation works before importing data. Bank lookup reports `unavailable`,
and `/health/ready` returns 503. `/health/live` indicates reachability.

## Import Bundesbank data

1. Download the **uncompressed public TXT file** from the
   [official download page](https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/serviceangebot/bankleitzahlen/download-bankleitzahlen-602592)
   and save it as `data/blz.txt`. This version does not accept CSV, XML, ZIP or the
   extended 174-character file.
2. Read the validity start and end dates on the download page. These dates are
   absent from the TXT rows and must be supplied during import.
3. Run the import. Example for the file offered on 5 October 2026:

```bash
openiban import-bundesbank data/blz.txt --valid-from 2026-09-07 --valid-until 2026-12-06
```

For later downloads, **use the corresponding dates**. Optionally, `--source-url`
records the actual Bundesbank HTTPS download URL. Import performs no network
requests and does not verify the origin of the local file. SHA-256 identifies
repeated files; it is not a signature.

Output includes the version, SHA-256, record count and counts of added, removed
and changed active banks compared with the currently active version. Review this
summary and provenance before activation. Even a formally valid file may be
incomplete; a complete review interface is not yet included.

```bash
openiban versions
openiban activate REPLACE-WITH-REPORTED-VERSION
```

Import and activation are separate. Identical files are not stored repeatedly.
Failed imports leave the existing dataset unchanged. Future versions can only
be activated from their validity start date. Dates are evaluated in `Europe/Berlin`.

For rollback, use the same activation command with an earlier version. Expired
versions also require `--allow-expired`; the API then explicitly reports `stale`
and returns no outdated bank mappings. Activation switches the version pointer
in a transaction rather than replacing parts of a live dataset.

Source files and local databases do not belong in the Git repository. Back them
up separately as needed. The database retains imported bank-code-owning records
and import/activation metadata. Branch records are validated and counted but
not stored.

## Try the API

```bash
curl -X POST http://127.0.0.1:8000/v1/validate \
  -H 'Content-Type: application/json' \
  -d '{"iban":"DE58 1234 5678 0123 4567 89"}'
```

This is a synthetic example. Its checksum is correct, but it does not represent
a real bank or account relationship. Against the official dataset, the response
may therefore contain `bank_lookup_status: not_found`.

| Field | Meaning |
|---|---|
| `normalized_iban` | Normalized input; no letters or punctuation removed |
| `country_supported` | Country format is supported |
| `iban_valid` | Country format and IBAN checksum; `null` for unsupported countries |
| `checks` | Individual format/checksum results; `null` means not checked |
| `reason` | `valid`, `invalid_format`, `invalid_characters`, `invalid_checksum`, `unsupported_country` |
| `bank_lookup_status` | `found`, `not_found`, `deleted`, `not_checked`, `unavailable`, `stale` |
| `bank_code_valid` | Bank code is valid in the current dataset; `null` means not checked/verifiable |
| `bank` | Bank data for an active match only; otherwise `null` |
| `data` | Dataset version, hash, source, import time and validity; otherwise `null` |

Validation results return HTTP 200, including invalid IBANs or missing bank data.
HTTP 422 indicates an invalid request format, 413 an oversized body, and 400
unsupported query parameters. Clients must evaluate the result fields.
`GET /v1/countries` lists supported countries.

## Tests

```bash
ruff check .
ruff format --check .
pytest -q
```

Tests use only synthetic records and require no network connection or Bundesbank
downloads. `requirements-dev.lock` pins development dependencies. Update it with:

```bash
uv pip compile pyproject.toml --extra dev --python-version 3.12 --output-file requirements-dev.lock
```

## Data source, license and next steps

**German source: Deutsche Bundesbank.** See
[Sources and terms of use](docs/data-sources.md).
The code is licensed under the [MIT License](LICENSE).
Copyright (c) 2026 Sebastian Arnold. Bundesbank data terms apply independently;
the MIT License grants no additional rights to that data.

The API runs at https://api.openiban.eu on an Ubuntu server at Hetzner.
Nginx provides HTTPS and rate limits. The lima-city website and protected
maintainer area are still planned. Details: [Roadmap](docs/roadmap.md) and
[Operations](docs/operations.md).

Email warnings: [Installation and operations](deployment/notifications/README.md).
SMTP credentials and recipients are configured exclusively on the server.

## Automatic Bundesbank updates (0.2.0)

Daily downloads, quality checks and activation from the validity start date are
available through the local maintainer CLI and systemd timers. Installation,
thresholds, monitoring and rollback: [deployment/auto-update/README.md](deployment/auto-update/README.md).
