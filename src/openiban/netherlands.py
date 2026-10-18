"""Daily full snapshot checks; RSS is informational, never a completeness gate."""

from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete, insert, select

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

DISCLAIMER = (
    "Source: Betaalvereniging Nederland. Dutch BICs and bank codes may be changed, "
    "revoked or added at any time. The list is carefully maintained, but no guarantee "
    "of accuracy is provided. Inclusion is voluntary and the list may be incomplete."
)


def update_nl(engine, state_dir: Path) -> dict:
    with locked(state_dir):
        content, url = download_directory("NL")
        parsed = parse_directory("NL", content)
        now = datetime.now(UTC)
        if not parsed.published_on or parsed.published_on > now.date():
            raise ValueError("Missing or future Dutch publication date.")
        with engine.connect() as conn:
            previous = conn.execute(
                select(active.c.dataset_id).where(active.c.country == "NL")
            ).scalar_one()
            old = conn.execute(select(versions).where(versions.c.id == previous)).mappings().first()
            old_records = {
                r.bank_code: (r.name, r.bic)
                for r in conn.execute(select(records).where(records.c.dataset_id == previous))
            }
        if old and parsed.published_on < old["valid_from"]:
            raise ValueError("Dutch source date moved backwards; review required.")
        new_records = {r.bank_code: (r.name, r.bic) for r in parsed.records}
        changed = sum(
            old_records.get(k) != new_records.get(k)
            for k in old_records.keys() | new_records.keys()
        )
        # Bootstrap also requires a plausible complete snapshot. Reject large
        # additions, removals and changed mappings; maintainers can review/stage.
        if not 50 <= len(new_records) <= 1000 or (
            old_records and changed / len(old_records) > 0.10
        ):
            raise ValueError("Dutch snapshot failed size/change checks; manual review required.")
        with TemporaryDirectory(dir=state_dir) as temporary:
            path = Path(temporary) / "nl.xlsx"
            path.write_bytes(content)
            staged = stage_directory(engine, "NL", path, parsed.published_on, date.max, url)
        # Serialize activation and freshness in one transaction. Lock the country
        # row before comparing, including bootstrap where previous is None.
        with engine.begin() as conn:
            from sqlalchemy import update

            conn.execute(
                update(active)
                .where(active.c.country == "NL")
                .values(dataset_id=active.c.dataset_id)
            )
            current = conn.execute(
                select(active.c.dataset_id).where(active.c.country == "NL")
            ).scalar_one()
            if current != previous:
                raise ValueError("Active Dutch dataset changed concurrently; retry later.")
            if current != staged["version"]:
                activate_directory(
                    conn,
                    "NL",
                    staged["version"],
                    review_note=(
                        "Automated official snapshot; permission supplied by maintainer, "
                        "attribution and disclaimer included; size/change checks passed."
                    ),
                )
            conn.execute(delete(checks).where(checks.c.country == "NL"))
            conn.execute(
                insert(checks).values(
                    country="NL", dataset_id=staged["version"], checked_at=now.isoformat()
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
            "disclaimer": DISCLAIMER,
        }
