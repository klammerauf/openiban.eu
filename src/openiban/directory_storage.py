"""Additive schema: immutable versions and independent activation per country.

The German tables and updater retain their schema and semantics.
"""

import hashlib
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from openiban.directories import MAX_BYTES, SOURCES, parse_directory
from openiban.directory_download import validate_url
from openiban.storage import dataset_status, metadata, today

versions = Table(
    "directory_versions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("country", String(2), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("valid_until", Date, nullable=False),
    Column("imported_at", String(40), nullable=False),
    Column("source_url", String(1000), nullable=False),
    Column("total_rows", Integer, nullable=False),
    Column("bank_rows", Integer, nullable=False),
    UniqueConstraint("country", "sha256"),
)
records = Table(
    "directory_banks",
    metadata,
    Column("dataset_id", ForeignKey("directory_versions.id"), primary_key=True),
    Column("bank_code", String(8), primary_key=True),
    Column("name", String(300), nullable=False),
    Column("bic", String(11)),
    Column("postal_code", String(32), nullable=False),
    Column("city", String(200), nullable=False),
    Column("change_flag", String(1), nullable=False),
    Column("deletion_announced", Integer, nullable=False),
    Column("successor_bank_code", String(8)),
)
active = Table(
    "directory_active",
    metadata,
    Column("country", String(2), primary_key=True),
    Column("dataset_id", ForeignKey("directory_versions.id")),
)
history = Table(
    "directory_activations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("country", String(2), nullable=False),
    Column("previous_id", String(36)),
    Column("dataset_id", ForeignKey("directory_versions.id"), nullable=False),
    Column("activated_at", String(40), nullable=False),
    Column("review_note", String(2000), nullable=False),
)


def initialize_directories(engine: Engine) -> None:
    # Separate additive tables; safe on databases created by older releases.
    metadata.create_all(engine, tables=[versions, records, active, history])
    with engine.begin() as conn:
        existing = set(conn.execute(select(active.c.country)).scalars())
        for country in SOURCES.keys() - existing:
            conn.execute(insert(active).values(country=country, dataset_id=None))


def stage_directory(
    engine: Engine, country: str, path: Path, valid_from: date, valid_until: date, source_url: str
) -> dict:
    validate_url(country, source_url)
    if valid_until < valid_from:
        raise ValueError("Validity end date precedes the start date.")
    with path.open("rb") as handle:
        content = handle.read(MAX_BYTES + 1)
    parsed = parse_directory(country, content)
    if parsed.published_on and valid_from < parsed.published_on:
        raise ValueError("Validity start date precedes the official source date.")
    digest = hashlib.sha256(content).hexdigest()
    with engine.begin() as conn:
        existing = (
            conn.execute(
                select(versions).where(versions.c.country == country, versions.c.sha256 == digest)
            )
            .mappings()
            .first()
        )
        if existing:
            if (
                existing["valid_from"] != valid_from
                or existing["valid_until"] != valid_until
                or existing["source_url"] != source_url
            ):
                raise ValueError("Identical file with different provenance or validity.")
            return {
                "version": existing["id"],
                "country": country,
                "already_imported": True,
                "bank_rows": existing["bank_rows"],
            }
        current = conn.execute(
            select(active.c.dataset_id).where(active.c.country == country)
        ).scalar_one()
        old = {
            r["bank_code"]: dict(r)
            for r in conn.execute(select(records).where(records.c.dataset_id == current)).mappings()
        }
        new = {r.bank_code: asdict(r) for r in parsed.records}
        old_keys = {k for k, r in old.items() if r["change_flag"] != "D"}
        new_keys = {k for k, r in new.items() if r["change_flag"] != "D"}
        changed = sum(any(old[k][f] != new[k][f] for f in new[k]) for k in old_keys & new_keys)
        version = str(uuid4())
        conn.execute(
            insert(versions).values(
                id=version,
                country=country,
                sha256=digest,
                valid_from=valid_from,
                valid_until=valid_until,
                source_url=source_url,
                imported_at=datetime.now(UTC).isoformat(),
                total_rows=parsed.total_rows,
                bank_rows=len(new),
            )
        )
        conn.execute(insert(records), [{"dataset_id": version, **r} for r in new.values()])
        return {
            "version": version,
            "country": country,
            "sha256": digest,
            "already_imported": False,
            "bank_rows": len(new),
            "total_rows": parsed.total_rows,
            "ignored_rows": parsed.ignored_rows,
            "added": len(new_keys - old_keys),
            "removed": len(old_keys - new_keys),
            "changed": changed,
            "comparison_version": current,
        }


def activate_directory(
    engine: Engine,
    country: str,
    version: str,
    *,
    review_note: str,
    allow_expired: bool = False,
    on_date: date | None = None,
    expected_previous_id: str | None = None,
) -> None:
    if country not in SOURCES or not review_note.strip() or len(review_note) > 2000:
        raise ValueError("Country and documented source/usage review required.")
    with engine.begin() as conn:
        conn.execute(
            update(active).where(active.c.country == country).values(dataset_id=active.c.dataset_id)
        )
        row = (
            conn.execute(
                select(versions).where(versions.c.id == version, versions.c.country == country)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ValueError("Unknown version for this country.")
        status = dataset_status(dict(row), on_date or today())
        if status == "not_yet_valid" or (status == "expired" and not allow_expired):
            raise ValueError("Version is not yet valid or has expired.")
        previous = conn.execute(
            select(active.c.dataset_id).where(active.c.country == country)
        ).scalar_one()
        if expected_previous_id is not None and expected_previous_id != previous:
            raise ValueError("Active dataset has changed.")
        conn.execute(update(active).where(active.c.country == country).values(dataset_id=version))
        conn.execute(
            insert(history).values(
                id=str(uuid4()),
                country=country,
                previous_id=previous,
                dataset_id=version,
                activated_at=datetime.now(UTC).isoformat(),
                review_note=review_note.strip(),
            )
        )


def lookup_directory(
    engine: Engine, country: str, bank_code: str, on_date: date | None = None
) -> tuple:
    with engine.connect() as conn:
        version = (
            conn.execute(
                select(versions)
                .join(active, active.c.dataset_id == versions.c.id)
                .where(active.c.country == country)
            )
            .mappings()
            .first()
        )
        if version is None:
            return None, None
        info = {
            "version": version["id"],
            "sha256": version["sha256"],
            "valid_from": version["valid_from"],
            "valid_until": version["valid_until"],
            "status": dataset_status(dict(version), on_date or today()),
            "source": "Source: " + SOURCES[country].publisher,
            "source_url": version["source_url"],
            "imported_at": version["imported_at"],
        }
        bank = None
        if info["status"] == "current":
            # SI: exact five-digit issuer code first, otherwise two-digit bank prefix.
            codes = [bank_code, bank_code[:2]] if country == "SI" else [bank_code]
            for code in codes:
                row = (
                    conn.execute(
                        select(records).where(
                            records.c.dataset_id == version["id"], records.c.bank_code == code
                        )
                    )
                    .mappings()
                    .first()
                )
                if row:
                    bank = dict(row)
                    break
        return info, bank


def list_directory_versions(engine: Engine, country: str) -> list[dict]:
    if country not in SOURCES:
        raise ValueError("Unknown country.")
    with engine.connect() as conn:
        current = conn.execute(
            select(active.c.dataset_id).where(active.c.country == country)
        ).scalar_one()
        return [
            {**dict(r), "active": r["id"] == current}
            for r in conn.execute(
                select(versions)
                .where(versions.c.country == country)
                .order_by(versions.c.imported_at)
            ).mappings()
        ]
