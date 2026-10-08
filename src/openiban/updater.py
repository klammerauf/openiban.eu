"""Conservative automation for the official Bundesbank TXT feed (Linux CLI).

Downloads are staged; a separate command activates eligible, recently checked
versions. State is atomically replaced and both jobs share an advisory lock.
"""

import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from sqlalchemy import select

from openiban.bundesbank import MAX_FILE_BYTES, SOURCE_URL, parse_txt
from openiban.storage import activate, activations, active_dataset, banks, datasets, stage_file

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_CHECK_AGE = timedelta(hours=48)
MIN_ACTIVE_BANKS = 1000
MAX_CHANGE_FRACTION = 0.10
BERLIN = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class Download:
    url: str
    valid_from: date
    valid_until: date


def allowed_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.bundesbank.de", "bundesbank.de"}
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or len(url) > 1000
    ):
        raise ValueError("Download or redirect outside allowed Bundesbank HTTPS addresses.")
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_bytes(url: str, limit: int) -> bytes:
    request = Request(
        allowed_url(url),
        headers={
            "User-Agent": "OpenIBAN.eu/0.2 (+https://openiban.eu)",
            "Accept-Encoding": "identity",
        },
    )
    deadline = time.monotonic() + 90
    with build_opener(SafeRedirect()).open(request, timeout=20) as response:
        allowed_url(response.geturl())
        if response.status != 200:
            raise ValueError("Unexpected HTTP status during Bundesbank download.")
        content = bytearray()
        while True:
            block = response.read(min(65536, limit + 1 - len(content)))
            content.extend(block)
            if len(content) > limit:
                raise ValueError("Bundesbank download exceeds the allowed file size.")
            if time.monotonic() > deadline:
                raise TimeoutError("Bundesbank download time limit exceeded.")
            if not block:
                return bytes(content)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join(" ".join(self.parts).split())))
            self.href = None


def quarter_start(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(5 - first.weekday()) % 7 + 2)


def validate_period(start: date, end: date) -> None:
    if start.month not in {3, 6, 9, 12} or start != quarter_start(start.year, start.month):
        raise ValueError("Unknown validity start date; manual review required.")
    next_start = (
        quarter_start(start.year + 1, 3)
        if start.month == 12
        else quarter_start(start.year, start.month + 3)
    )
    if end != next_start - timedelta(days=1):
        raise ValueError("Unknown validity end date; manual review required.")


def discover(html: str, on_date: date) -> list[Download]:
    parser = Links()
    parser.feed(html)
    found = {}
    periods = {}
    for href, label in parser.links:
        path = urlsplit(href).path.lower()
        if not path.endswith(".txt") or "bankleitzahlendatei" not in label.lower():
            continue
        url = allowed_url(urljoin(SOURCE_URL, href))
        if not urlsplit(url).path.startswith("/resource/blob/"):
            raise ValueError("Unknown TXT download path.")
        matches = re.findall(
            r"gültig vom\s+(\d{2}\.\d{2}\.\d{4})\s+bis\s+(\d{2}\.\d{2}\.\d{4})", label, re.I
        )
        if len(matches) != 1:
            raise ValueError("TXT link without an unambiguous validity period.")
        start, end = (datetime.strptime(value, "%d.%m.%Y").date() for value in matches[0])
        validate_period(start, end)
        if end < on_date:
            continue
        if start > on_date + timedelta(days=120):
            raise ValueError("Download is dated unusually far in the future.")
        item = Download(url, start, end)
        if url in found and found[url] != item:
            raise ValueError("The same download link has conflicting validity dates.")
        if (start, end) in periods and periods[start, end] != url:
            raise ValueError("Multiple TXT links for the same period; manual review required.")
        found[url] = item
        periods[start, end] = url
    if not found or len(found) > 2:
        raise ValueError("Expected one or two current or future TXT downloads.")
    result = sorted(found.values(), key=lambda item: item.valid_from)
    if len(result) == 2 and result[0].valid_until + timedelta(days=1) != result[1].valid_from:
        raise ValueError("Gap between available validity periods.")
    return result


@contextmanager
def locked(directory: Path):
    import fcntl

    directory.mkdir(parents=True, exist_ok=True, mode=0o750)
    with (directory / ".lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another updater run is still active.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_state(directory: Path) -> dict:
    path = directory / "state.json"
    if not path.exists():
        return {"schema": 1, "candidates": [], "quarantine": {}}
    state = json.loads(path.read_text())
    if state.get("schema") != 1 or not isinstance(state.get("candidates"), list):
        raise ValueError("Unknown or damaged updater status format.")
    return state


def save_state(directory: Path, state: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", dir=directory, delete=False, encoding="utf-8"
    ) as file:
        temporary = Path(file.name)
        try:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(directory / "state.json")
    finally:
        temporary.unlink(missing_ok=True)


def snapshot(engine, version_id: str | None = None) -> tuple[dict | None, dict]:
    with engine.connect() as conn:
        if version_id is None:
            version_id = conn.execute(
                select(active_dataset.c.dataset_id).where(active_dataset.c.id == 1)
            ).scalar_one()
        if version_id is None:
            return None, {}
        row = conn.execute(select(datasets).where(datasets.c.id == version_id)).mappings().one()
        records = {
            r["bank_code"]: dict(r)
            for r in conn.execute(select(banks).where(banks.c.dataset_id == version_id)).mappings()
        }
        return dict(row), records


def quality(old: dict, new: dict, old_total: int, new_total: int) -> tuple[dict, list[str]]:
    old = {key: value for key, value in old.items() if value["change_flag"] != "D"}
    new = {key: value for key, value in new.items() if value["change_flag"] != "D"}
    common = old.keys() & new.keys()
    fields = ("name", "postal_code", "city", "bic", "deletion_announced", "successor_bank_code")
    counts = {
        "active_banks": len(new),
        "added": len(new.keys() - old.keys()),
        "removed": len(old.keys() - new.keys()),
        "changed": sum(
            any(old[key][field] != new[key][field] for field in fields) for key in common
        ),
    }
    reasons = []
    if len(new) < MIN_ACTIVE_BANKS:
        reasons.append(f"Fewer than {MIN_ACTIVE_BANKS} active banks.")
    if old_total and not 0.8 <= new_total / old_total <= 1.25:
        reasons.append("Total row count differs by more than -20/+25 percent.")
    if not old:
        reasons.append("No active reference dataset available.")
    else:
        for metric in ("added", "removed", "changed"):
            if counts[metric] / len(old) > MAX_CHANGE_FRACTION:
                reasons.append(f"{metric}: more than 10 percent of the active dataset affected.")
        old_missing = sum(not record["bic"] for record in old.values())
        new_missing = sum(not record["bic"] for record in new.values())
        if new_missing > old_missing + max(10, int(len(old) * 0.05)):
            reasons.append("Unusually many additional records without a BIC.")
    return counts, reasons


def health_warnings(engine, state: dict, now: datetime) -> list[str]:
    on_date = now.astimezone(BERLIN).date()
    warnings = []
    if state.get("last_check_error"):
        warnings.append("Last download failed: " + state["last_check_error"])
    checked = state.get("last_successful_check")
    if not checked or not timedelta(0) <= now - datetime.fromisoformat(checked) <= MAX_CHECK_AGE:
        warnings.append("No successful download within the last 48 hours.")
    if any(item["status"] == "needs_review" for item in state["candidates"]):
        warnings.append("At least one available dataset version requires manual review.")
    current, _ = snapshot(engine)
    if current is None:
        warnings.append("No active bank dataset.")
    elif current["valid_until"] < on_date:
        warnings.append("Active bank dataset has expired.")
    elif current["valid_until"] - on_date <= timedelta(days=14):
        successor_ready = any(
            item["status"] == "approved"
            and date.fromisoformat(item["valid_from"]) == current["valid_until"] + timedelta(days=1)
            for item in state["candidates"]
        )
        if not successor_ready:
            warnings.append("Active dataset expires within 14 days; no reviewed successor.")
    return warnings


def auto_check(
    engine, directory: Path, *, now: datetime | None = None, fetch=download_bytes
) -> dict:
    now = now or datetime.now(UTC)
    on_date = now.astimezone(BERLIN).date()
    with locked(directory):
        state = read_state(directory)
        state["last_attempt"] = now.isoformat()
        try:
            html = fetch(SOURCE_URL, MAX_PAGE_BYTES).decode("utf-8")
            downloads = discover(html, on_date)
            current, current_banks = snapshot(engine)
            if current is None:
                raise ValueError("Manually import and activate an initial dataset first.")
            candidates = []
            for item in downloads:
                data = fetch(item.url, MAX_FILE_BYTES)
                parsed = parse_txt(data)
                digest = hashlib.sha256(data).hexdigest()
                archive = directory / f"{digest}.txt"
                if not archive.exists():
                    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as file:
                        temporary = Path(file.name)
                        file.write(data)
                    temporary.replace(archive)
                # Always stage the bytes just downloaded, never trust a modified cache file.
                if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
                    raise ValueError("Local download copy has a different checksum.")
                result = stage_file(engine, archive, item.valid_from, item.valid_until, item.url)
                version_id = result["version"]
                _, new_banks = snapshot(engine, version_id)
                counts, reasons = quality(
                    current_banks, new_banks, current["total_rows"], parsed.total_rows
                )
                if version_id == current["id"]:
                    status, reasons = "current", []
                elif item.valid_from <= current["valid_from"]:
                    status = "needs_review"
                    reasons.append("Older or different dataset for the same period.")
                else:
                    if digest in state["quarantine"]:
                        reasons.append("This file was already held for manual review.")
                    status = "needs_review" if reasons else "approved"
                if status == "needs_review":
                    state["quarantine"][digest] = reasons
                candidates.append(
                    {
                        "version": version_id,
                        "sha256": digest,
                        "source_url": item.url,
                        "valid_from": item.valid_from.isoformat(),
                        "valid_until": item.valid_until.isoformat(),
                        "status": status,
                        "reasons": reasons,
                        "counts": counts,
                        "comparison_version": current["id"],
                    }
                )
            state["candidates"] = candidates
            state["last_successful_check"] = now.isoformat()
            state["last_check_error"] = None
        except Exception as exc:
            state["last_check_error"] = str(exc)[:1000]
            save_state(directory, state)
            raise
        state["warnings"] = health_warnings(engine, state, now)
        save_state(directory, state)
        return state


def auto_activate(engine, directory: Path, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    on_date = now.astimezone(BERLIN).date()
    with locked(directory):
        state = read_state(directory)
        checked = state.get("last_successful_check")
        if (
            state.get("last_check_error")
            or not checked
            or not timedelta(0) <= now - datetime.fromisoformat(checked) <= MAX_CHECK_AGE
        ):
            raise ValueError("Activation blocked: perform a successful recent download first.")
        current, current_banks = snapshot(engine)
        if current is None:
            raise ValueError("No active reference dataset.")
        with engine.connect() as conn:
            previously_activated = set(conn.execute(select(activations.c.dataset_id)).scalars())
        eligible = [
            item
            for item in state["candidates"]
            if item["status"] == "approved"
            and item["version"] not in previously_activated
            and date.fromisoformat(item["valid_from"])
            <= on_date
            <= date.fromisoformat(item["valid_until"])
        ]
        outcome = "no_change"
        if eligible:
            item = max(eligible, key=lambda value: value["valid_from"])
            version, records = snapshot(engine, item["version"])
            if (
                item["comparison_version"] != current["id"]
                or version["valid_from"] <= current["valid_from"]
                or version["sha256"] != item["sha256"]
                or version["valid_from"].isoformat() != item["valid_from"]
                or version["valid_until"].isoformat() != item["valid_until"]
            ):
                raise ValueError("Reference dataset or candidate changed: download again.")
            _, reasons = quality(
                current_banks, records, current["total_rows"], version["total_rows"]
            )
            if reasons:
                item["status"] = "needs_review"
                item["reasons"] = reasons
                state["quarantine"][item["sha256"]] = reasons
                save_state(directory, state)
                raise ValueError("Repeated quality check failed: " + "; ".join(reasons))
            activate(engine, item["version"], on_date=on_date, expected_previous_id=current["id"])
            item["status"] = "current"
            state["last_activation"] = {
                "at": now.isoformat(),
                "version": item["version"],
                "previous": current["id"],
            }
            outcome = "activated"
        state["warnings"] = health_warnings(engine, state, now)
        save_state(directory, state)
        return {
            "result": outcome,
            "last_activation": state.get("last_activation"),
            "warnings": state["warnings"],
        }


def update_status(engine, directory: Path, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    state = read_state(directory)
    state["warnings"] = health_warnings(engine, state, now)
    return state
