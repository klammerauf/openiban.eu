# Operating the initial implementation

## Local operation

The API and import CLI share database configuration. Create the schema once with
`openiban init-db`, then start the API. `init-db` can be repeated, but is not a
future schema migration tool. A local maintainer performs imports and activations;
avoid concurrent initialization. Database access is equivalent to administrative access.

The API does not store or log IBAN requests. The documented startup command
disables standard server access logs; error responses do not echo input.
Responses carry `Cache-Control: no-store`. IBANs belong exclusively in the JSON
body. Rejecting query parameters does not prevent upstream systems from already
logging URLs.

## Data approval and recovery

1. Download files exclusively from the official Bundesbank website.
2. Review validity and the import report; investigate unusual changes.
3. Explicitly activate the version; future data becomes active on its validity
   start date only when automation is configured.
4. Check `/health/ready` and a known test query.
5. On failure, activate the previous version; expired data remains identifiable
   as expired and is not returned as a valid bank mapping.

To back up SQLite, stop API and import processes and copy `data/openiban.db`, or
use SQLite's backup mechanism. Test restoration in a separate environment.
Configure a suitable backup/restore procedure for PostgreSQL. Retain source
files separately if identical reconstruction may be needed later.

## Deployed operation

As of 8 October 2026: API on Ubuntu 24.04 at Hetzner, Python 3.12, systemd service
`openiban`, SQLite at `/var/lib/openiban/openiban.db`. Nginx forwards requests to
`127.0.0.1:8000`, applies rate limits and terminates HTTPS. Certificate renewal
and local daily SQLite backups have been checked.

- [Automatic data updates](../deployment/auto-update/README.md)
- [SMTP warnings](../deployment/notifications/README.md)

Installation scripts assume the existing API and backup service; they do not
provide a complete installation on an empty server. The update installer expects
a wheel in its `wheels` subdirectory. When installing from Git, build it first:

```bash
python -m pip wheel --no-deps . -w deployment/auto-update/wheels
```

External backups, a recovery test and external availability monitoring remain
outstanding. The local email monitor cannot report a complete outage of its own
server. The code is licensed under MIT. Operator and privacy notices remain to
be defined. The website is planned at lima-city.
