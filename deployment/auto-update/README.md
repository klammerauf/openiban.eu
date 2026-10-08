# Automatic updates – version 0.2.0

For the existing installation at `/opt/openiban.eu`, user `openiban`, SQLite at
`/var/lib/openiban/openiban.db` and `openiban-backup.service`.

Extract the ZIP in your home directory and run:

```bash
unzip -q ~/OpenIBAN-API-v0.2.0.zip -d ~/openiban-update-v0.2.0
sudo bash ~/openiban-update-v0.2.0/openiban.eu/deployment/auto-update/install.sh
```

The script backs up the database using the existing backup service and saves
the Python environment at `/var/backups/openiban-update/<timestamp>/venv`.
It installs the included wheel without new dependencies, briefly restarts the
API, checks reachability and configures timers. Nginx remains unchanged.
The extracted directory includes the corresponding complete source code.
Installed Python code resides in the existing venv; the older source copy at
`/opt/openiban.eu/src` is not overwritten. Use the new source version for later development.

## Workflow

- Daily at 04:15 Europe/Berlin: read the official download page, download current
  and future TXT files, validate, import versions and activate data already due.
- Daily at 00:05: activate staged data on its validity start date. No API restart needed.
- Missed timer runs are caught up after server startup.
- Downloads and redirects use HTTPS on bundesbank.de/www.bundesbank.de only.
- Dates come from the official page. Unknown quarterly periods, ambiguous links,
  damaged files and checksum conflicts stop the run.
- Automatic approval requires at least 1,000 active banks. More than 10% added,
  removed or changed banks, unusual BIC loss, or row-count changes outside
  -20/+25% require manual review. These are technical safeguards, not Bundesbank rules.
- A download failure or a last successful download more than 48 hours ago blocks
  automatic activation. The existing dataset is retained; expired data continues
  to be treated as stale by the API.
- A different file for the same period is not replaced automatically. Previously
  activated versions are not automatically reactivated after a manual rollback.
- The same file checksum with different validity dates requires manual resolution
  because of the existing unique-hash data model; no automatic date reassignment.

## Monitoring

```bash
sudo journalctl -u openiban-update-check.service -u openiban-update-activate.service -n 80 --no-pager
sudo -u openiban env OPENIBAN_DATABASE_URL=sqlite:////var/lib/openiban/openiban.db /opt/openiban.eu/.venv/bin/openiban update-status
systemctl list-timers 'openiban-update-*' --no-pager
```

Exit codes: 0 success, 1 error, 2 warning. Warnings appear in JSON/the journal
and mark the corresponding service as failed. Timers retry on their next schedule.
**The updater itself sends no email or push notification.** Check the journal/status
regularly until monitoring is configured. A warning is raised when fewer than
14 days of validity remain without an approved successor.

Files and atomically saved state reside at `/var/lib/openiban/updates`.
The existing database backup includes imported versions, but excludes this state
and TXT copies. A fresh download can rebuild them; any lost manual hold must be
reviewed again. Include this directory and configuration in external backups
for complete recovery.

## Manual review

`update-status` lists candidate IDs, change counts and reasons. After reviewing
the data, and from its validity start date, use the existing CLI:

```bash
sudo -u openiban env OPENIBAN_DATABASE_URL=sqlite:////var/lib/openiban/openiban.db /opt/openiban.eu/.venv/bin/openiban activate VERSION-ID
sudo systemctl start openiban-update-check.service
```

## Stop automation / roll back code

```bash
sudo systemctl disable --now openiban-update-check.timer openiban-update-activate.timer
sudo systemctl stop openiban-update-check.service openiban-update-activate.service
```

For code rollback, stop the API, move the current `/opt/openiban.eu/.venv` aside
and use `cp -a` to restore the installer's reported `venv` backup to **its original
path**, `/opt/openiban.eu/.venv`. Then start the API. Version 0.2.0 did not change
the database schema. Roll back data separately using the existing `activate` CLI;
this does not make old data current again.
