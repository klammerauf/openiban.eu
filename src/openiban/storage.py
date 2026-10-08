"""Immutable dataset versions and a transactional active-version pointer."""

import hashlib
import os
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine, make_url

from openiban.bundesbank import ATTRIBUTION, MAX_FILE_BYTES, SOURCE_URL, parse_txt

metadata = MetaData()
datasets = Table(
    "datasets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("valid_from", Date, nullable=False),
    Column("valid_until", Date, nullable=False),
    Column("imported_at", String(40), nullable=False),
    Column("source_url", String(1000), nullable=False),
    Column("total_rows", Integer, nullable=False),
    Column("bank_rows", Integer, nullable=False),
)
banks = Table(
    "banks",
    metadata,
    Column("dataset_id", ForeignKey("datasets.id"), primary_key=True),
    Column("bank_code", String(8), primary_key=True),
    Column("name", String(58), nullable=False),
    Column("postal_code", String(5), nullable=False),
    Column("city", String(35), nullable=False),
    Column("bic", String(11)),
    Column("record_number", String(6), nullable=False),
    Column("change_flag", String(1), nullable=False),
    Column("deletion_announced", Boolean, nullable=False),
    Column("successor_bank_code", String(8)),
    UniqueConstraint("dataset_id", "record_number"),
)
active_dataset = Table(
    "active_dataset",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", ForeignKey("datasets.id")),
)
activations = Table(
    "activations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("previous_id", String(36)),
    Column("dataset_id", ForeignKey("datasets.id"), nullable=False),
    Column("activated_at", String(40), nullable=False),
)


def today() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def build_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("OPENIBAN_DATABASE_URL", "sqlite:///data/openiban.db")
    parsed = make_url(url)
    kwargs = {}
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    return create_engine(url, pool_pre_ping=True, **kwargs)


def initialize(engine: Engine) -> None:
    # Initial schema only; future changes require migrations. Run before serving.
    metadata.create_all(engine)
    with engine.begin() as conn:
        if (
            conn.execute(select(active_dataset.c.id).where(active_dataset.c.id == 1)).first()
            is None
        ):
            conn.execute(insert(active_dataset).values(id=1, dataset_id=None))


def dataset_status(row: dict, on_date: date) -> str:
    if on_date < row["valid_from"]:
        return "not_yet_valid"
    if on_date > row["valid_until"]:
        return "expired"
    return "current"


def dataset_info(row: dict, on_date: date) -> dict:
    return {
        "version": row["id"],
        "sha256": row["sha256"],
        "valid_from": row["valid_from"],
        "valid_until": row["valid_until"],
        "status": dataset_status(row, on_date),
        "source": ATTRIBUTION,
        "source_url": row["source_url"],
        "imported_at": row["imported_at"],
    }


def lookup(engine: Engine, bank_code: str | None, on_date: date | None = None) -> tuple:
    on_date = on_date or today()
    with engine.connect() as conn:
        version_id = conn.execute(
            select(active_dataset.c.dataset_id).where(active_dataset.c.id == 1)
        ).scalar_one_or_none()
        if version_id is None:
            return None, None
        version = dict(
            conn.execute(select(datasets).where(datasets.c.id == version_id)).mappings().one()
        )
        bank = None
        if bank_code and dataset_status(version, on_date) == "current":
            row = (
                conn.execute(
                    select(banks).where(
                        banks.c.dataset_id == version_id, banks.c.bank_code == bank_code
                    )
                )
                .mappings()
                .first()
            )
            if row:
                bank = dict(row)
        return dataset_info(version, on_date), bank


def stage_file(
    engine: Engine, path: Path, valid_from: date, valid_until: date, source_url: str = SOURCE_URL
) -> dict:
    if valid_until < valid_from:
        raise ValueError("Validity end date precedes the start date.")
    parsed_url = urlsplit(source_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in {"bundesbank.de", "www.bundesbank.de"}
        or parsed_url.username
        or parsed_url.password
        or len(source_url) > 1000
    ):
        raise ValueError("Source URL must be a Bundesbank HTTPS address.")
    with path.open("rb") as handle:
        content = handle.read(MAX_FILE_BYTES + 1)
    parsed = parse_txt(content)
    digest = hashlib.sha256(content).hexdigest()
    with engine.begin() as conn:
        existing = (
            conn.execute(select(datasets).where(datasets.c.sha256 == digest)).mappings().first()
        )
        if existing:
            if existing["valid_from"] != valid_from or existing["valid_until"] != valid_until:
                raise ValueError(
                    "Identical file was already imported with a different validity period."
                )
            return {
                "version": existing["id"],
                "already_imported": True,
                "total_rows": existing["total_rows"],
                "bank_rows": existing["bank_rows"],
            }
        version_id = str(uuid4())
        current_id = conn.execute(
            select(active_dataset.c.dataset_id).where(active_dataset.c.id == 1)
        ).scalar_one()
        old = {
            r["bank_code"]: dict(r)
            for r in conn.execute(select(banks).where(banks.c.dataset_id == current_id)).mappings()
        }
        new = {r.bank_code: asdict(r) for r in parsed.records}
        active_new = {key for key, r in new.items() if r["change_flag"] != "D"}
        active_old = {key for key, r in old.items() if r["change_flag"] != "D"}
        relevant = (
            "name",
            "postal_code",
            "city",
            "bic",
            "deletion_announced",
            "successor_bank_code",
        )
        changed = sum(
            any(old[key][field] != new[key][field] for field in relevant)
            for key in active_new & active_old
        )
        conn.execute(
            insert(datasets).values(
                id=version_id,
                sha256=digest,
                valid_from=valid_from,
                valid_until=valid_until,
                imported_at=datetime.now(UTC).isoformat(),
                source_url=source_url,
                total_rows=parsed.total_rows,
                bank_rows=len(parsed.records),
            )
        )
        conn.execute(insert(banks), [{"dataset_id": version_id, **r} for r in new.values()])
        return {
            "version": version_id,
            "sha256": digest,
            "already_imported": False,
            "total_rows": parsed.total_rows,
            "bank_rows": len(parsed.records),
            "ignored_branch_rows": parsed.ignored_branch_rows,
            "active_banks": len(active_new),
            "added": len(active_new - active_old),
            "removed": len(active_old - active_new),
            "changed": changed,
            "comparison_version": current_id,
        }


def activate(
    engine: Engine,
    version_id: str,
    *,
    allow_expired: bool = False,
    on_date: date | None = None,
    expected_previous_id: str | None = None,
) -> None:
    on_date = on_date or today()
    with engine.begin() as conn:
        # Serialize activations before reading the old pointer (also in SQLite).
        conn.execute(
            update(active_dataset)
            .where(active_dataset.c.id == 1)
            .values(dataset_id=active_dataset.c.dataset_id)
        )
        row = conn.execute(select(datasets).where(datasets.c.id == version_id)).mappings().first()
        if row is None:
            raise ValueError("Unknown dataset version.")
        status = dataset_status(dict(row), on_date)
        if status == "not_yet_valid":
            raise ValueError("Dataset version is not yet valid.")
        if status == "expired" and not allow_expired:
            raise ValueError("Dataset version has expired; rollback requires --allow-expired.")
        previous_id = conn.execute(
            select(active_dataset.c.dataset_id).where(active_dataset.c.id == 1)
        ).scalar_one()
        if expected_previous_id is not None and previous_id != expected_previous_id:
            raise ValueError("Active dataset has changed. Repeat the review.")
        conn.execute(
            update(active_dataset).where(active_dataset.c.id == 1).values(dataset_id=version_id)
        )
        conn.execute(
            insert(activations).values(
                id=str(uuid4()),
                previous_id=previous_id,
                dataset_id=version_id,
                activated_at=datetime.now(UTC).isoformat(),
            )
        )


def list_versions(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        current_id = conn.execute(
            select(active_dataset.c.dataset_id).where(active_dataset.c.id == 1)
        ).scalar_one()
        return [
            {**dict(row), "active": row["id"] == current_id}
            for row in conn.execute(select(datasets).order_by(datasets.c.imported_at)).mappings()
        ]
