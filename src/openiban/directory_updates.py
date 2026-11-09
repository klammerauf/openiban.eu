"""Validated periodic updates for official bank directory snapshots."""

from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete, insert, select, update

from openiban.directories import parse_directory
from openiban.directory_download import download_directory
from openiban.directory_storage import (
    activate_directory,
    active,
    checks,
    records,
    stage_directory,
    versions,
)
from openiban.updater import locked

NL_DISCLAIMER = (
    "Source: Betaalvereniging Nederland. Dutch BICs and bank codes may be changed, "
    "revoked or added at any time. The list is carefully maintained, but no guarantee "
    "of accuracy is provided. Inclusion is voluntary and the list may be incomplete."
)


def update_nl(engine, state_dir: Path) -> dict:
    return update_directory(engine, state_dir, "NL")


def update_directory(engine, state_dir: Path, country: str) -> dict:
    minimum, maximum = {"NL": (50, 1000), "PL": (2000, 6000)}[country]
    with locked(state_dir):
        content, url = download_directory(country)
        parsed = parse_directory(country, content)
        now = datetime.now(UTC)
        if country == "NL" and (not parsed.published_on or parsed.published_on > now.date()):
            raise ValueError("Missing or future Dutch publication date.")
        with engine.connect() as conn:
            previous = conn.execute(
                select(active.c.dataset_id).where(active.c.country == country)
            ).scalar_one()
            old = conn.execute(select(versions).where(versions.c.id == previous)).mappings().first()
            old_records = {
                r.bank_code: (r.name, r.bic)
                for r in conn.execute(select(records).where(records.c.dataset_id == previous))
            }
            imported_from = conn.execute(
                select(versions.c.valid_from).where(
                    versions.c.country == country, versions.c.sha256 == sha256(content).hexdigest()
                )
            ).scalar_one_or_none()
        valid_from = parsed.published_on or imported_from or now.date()
        if old and parsed.published_on and parsed.published_on < old["valid_from"]:
            raise ValueError("Dutch source date moved backwards; review required.")
        new_records = {r.bank_code: (r.name, r.bic) for r in parsed.records}
        changed = sum(
            old_records.get(k) != new_records.get(k)
            for k in old_records.keys() | new_records.keys()
        )
        # Bootstrap also requires a plausible complete snapshot. Reject large
        # additions, removals and changed mappings; maintainers can review/stage.
        if not minimum <= len(new_records) <= maximum or (
            old_records and changed / len(old_records) > 0.10
        ):
            raise ValueError("Snapshot failed size/change checks; manual review required.")
        with TemporaryDirectory(dir=state_dir) as temporary:
            path = Path(temporary) / "snapshot"
            path.write_bytes(content)
            staged = stage_directory(engine, country, path, valid_from, date.max, url)
        # Serialize activation and freshness in one transaction. Lock the country
        # row before comparing, including bootstrap where previous is None.
        with engine.begin() as conn:
            conn.execute(
                update(active)
                .where(active.c.country == country)
                .values(dataset_id=active.c.dataset_id)
            )
            current = conn.execute(
                select(active.c.dataset_id).where(active.c.country == country)
            ).scalar_one()
            if current != previous:
                raise ValueError("Active directory dataset changed concurrently; retry later.")
            if current != staged["version"]:
                activate_directory(
                    conn,
                    country,
                    staged["version"],
                    review_note=(
                        "Automated official snapshot; permission supplied by maintainer, "
                        "attribution and disclaimer included; size/change checks passed."
                    ),
                )
            conn.execute(delete(checks).where(checks.c.country == country))
            conn.execute(
                insert(checks).values(
                    country=country, dataset_id=staged["version"], checked_at=now.isoformat()
                )
            )
        return {
            "status": "unchanged" if current == staged["version"] else "updated",
            "version": staged["version"],
            "published_on": parsed.published_on,
            "checked_at": now.isoformat(),
            "source_url": url,
            "bank_rows": len(new_records),
            "changed": changed,
            "disclaimer": NL_DISCLAIMER if country == "NL" else None,
        }
