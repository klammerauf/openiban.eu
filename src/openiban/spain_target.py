"""Offline, reviewed TARGET supplement; never downloads, writes a DB or activates data.

Poppler's pdftotext is needed only to prepare a bundle, not to stage it.
The bundle and original PDF must be retained together for provenance review.
"""

import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from dataclasses import replace
from datetime import date
from pathlib import Path

from openiban.directories import MAX_BYTES, Directory, parse_es

TARGET_URL = "https://www.bde.es/f/webbe/Comunes/sispago/menu_dcha/TARGET_BE_BIC.pdf"
SCHEMA = "openiban-es-target-v1"
FOOTNOTE = (
    "El * en el campo BIC11 indica que el participante ha solicitado la no "
    "publicación de su BIC en el directorio RTGS"
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_name(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value).upper()
        if c.isalnum() and not unicodedata.combining(c)
    )


def target_rows(value: str) -> list[dict]:
    """Accept every table line or reject the entire extraction, including truncation."""
    if len(value.encode()) > MAX_BYTES:
        raise ValueError("TARGET text too large.")
    pages = value.rstrip("\f\n ").split("\f")
    result, codes, bics = [], set(), set()
    for number, page in enumerate(pages, 1):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        if (
            len(lines) < 6
            or lines[:2]
            != ["PARTICIPANTES TITULARES CUENTA DCA RTGS", "EN TARGET - BANCO DE ESPAÑA"]
            or re.sub(r"\s+", " ", lines[2]) != "BIC 11 DENOMINACIÓN NRBE"
            or re.sub(r"\s+", " ", lines[-2]) != FOOTNOTE
            or lines[-1] != str(number)
        ):
            raise ValueError("Unknown or incomplete TARGET page structure.")
        for line in lines[3:-2]:
            match = re.fullmatch(r"(\*|[A-Z]{4}ES[A-Z0-9]{5})\s+(.+?)\s+([0-9]{4})", line)
            if not match:
                raise ValueError("Malformed TARGET row or BIC11.")
            bic, name, code = match.groups()
            if (
                code in codes
                or (bic != "*" and bic in bics)
                or len(name) > 300
                or any(ord(c) < 32 for c in name)
            ):
                raise ValueError("Duplicate or invalid TARGET record.")
            codes.add(code)
            if bic != "*":
                bics.add(bic)
            result.append(
                dict(nrbe=code, bic11=None if bic == "*" else bic, target_name=name, page=number)
            )
    if not result:
        raise ValueError("Empty TARGET table.")
    return result


def reconcile(mfi: bytes, target_text: str, reviews: list[dict], blocked: list[dict]):
    directory = parse_es(mfi)
    banks = {r.bank_code: r for r in directory.records}
    targets = {r["nrbe"]: r for r in target_rows(target_text)}
    decisions = {}
    for decision in reviews + blocked:
        if not isinstance(decision, dict) or set(decision) != {
            "nrbe",
            "target_name",
            "mfi_name",
            "bic11",
            "reason",
        }:
            raise ValueError("Unknown review schema.")
        code = decision["nrbe"]
        if (
            code in decisions
            or code not in banks
            or code not in targets
            or decision["target_name"] != targets[code]["target_name"]
            or decision["mfi_name"] != banks[code].name
            or decision["bic11"] != targets[code]["bic11"]
            or not isinstance(decision["reason"], str)
            or not decision["reason"].strip()
        ):
            raise ValueError("Review does not match these exact source rows.")
        decisions[code] = decision
    reviewed = {r["nrbe"] for r in reviews}
    excluded = {r["nrbe"] for r in blocked}
    rows, records = [], []
    for code in sorted(banks.keys() | targets.keys()):
        bank, target = banks.get(code), targets.get(code)
        same_name = bool(
            bank and target and normalize_name(bank.name) == normalize_name(target["target_name"])
        )
        if bank is None:
            status = "outside_mfi_credit_scope"
        elif target is None:
            status = "not_in_target"
        elif target["bic11"] is None:
            status = "not_published"
        elif code in excluded:
            status = "source_conflict"
        elif not same_name and code not in reviewed:
            status = "name_review_required"
        else:
            status = "matched" if same_name else "matched_reviewed_name"
        accepted = status in {"matched", "matched_reviewed_name"}
        value = target["bic11"] if accepted else None
        if bank:
            records.append(replace(bank, bic=value))
        rows.append(
            dict(
                nrbe=code,
                bic11=target["bic11"] if target else None,
                accepted_bic11=value,
                mfi_name=bank.name if bank else "",
                target_name=target["target_name"] if target else "",
                status=status,
                page=target["page"] if target else "",
                review_reason=decisions.get(code, {}).get("reason", ""),
            )
        )
    return Directory(records, directory.total_rows, directory.ignored_rows), rows


def parse_bundle(content: bytes) -> Directory:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate bundle JSON key.")
            result[key] = value
        return result

    try:
        bundle = json.loads(content, object_pairs_hook=unique)
        if (
            set(bundle)
            != {"schema", "mfi_csv", "target_text", "provenance", "name_reviews", "blocked"}
            or bundle["schema"] != SCHEMA
        ):
            raise ValueError("Unknown ES TARGET bundle schema.")
        mfi = bundle["mfi_csv"].encode("utf-8")
        if mfi.lstrip(b"\xef\xbb\xbf \r\n").startswith(b"{"):
            raise ValueError("Nested bundles are not allowed.")
        provenance = bundle["provenance"]
        if (
            provenance["target_url"] != TARGET_URL
            or provenance["mfi_sha256"] != sha256(mfi)
            or provenance["target_text_sha256"] != sha256(bundle["target_text"].encode())
            or not re.fullmatch("[0-9a-f]{64}", provenance["target_pdf_sha256"])
            or not isinstance(bundle["name_reviews"], list)
            or not isinstance(bundle["blocked"], list)
        ):
            raise ValueError("Invalid bundle provenance.")
        from openiban.directories import SOURCES

        if provenance["mfi_url"] != SOURCES["ES"].download:
            raise ValueError("Unexpected MFI source URL.")
        date.fromisoformat(provenance["retrieved_on"])
        return reconcile(mfi, bundle["target_text"], bundle["name_reviews"], bundle["blocked"])[0]
    except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid ES TARGET bundle.") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mfi", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="JSON with name_reviews, blocked and provenance metadata",
    )
    args = parser.parse_args()
    if max(args.mfi.stat().st_size, args.pdf.stat().st_size) > MAX_BYTES:
        parser.error("Source file too large.")
    mfi, pdf = args.mfi.read_bytes(), args.pdf.read_bytes()
    try:
        value = subprocess.run(
            ["pdftotext", "-layout", str(args.pdf.resolve()), "-"],
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        parser.error(f"Poppler extraction failed: {exc}")
    review = json.loads(args.review.read_text())
    from openiban.directories import SOURCES

    provenance = dict(
        review["provenance"],
        target_url=TARGET_URL,
        mfi_url=SOURCES["ES"].download,
        mfi_sha256=sha256(mfi),
        target_pdf_sha256=sha256(pdf),
        target_text_sha256=sha256(value.encode()),
    )
    bundle = dict(
        schema=SCHEMA,
        mfi_csv=mfi.decode("utf-8"),
        target_text=value,
        provenance=provenance,
        name_reviews=review["name_reviews"],
        blocked=review["blocked"],
    )
    encoded = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode()
    parsed = parse_bundle(encoded)
    _, rows = reconcile(mfi, value, bundle["name_reviews"], bundle["blocked"])
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "es-target-bundle.json").open("xb") as handle:
        handle.write(encoded)
    with (args.output / "es-bic-mapping.csv").open("x", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*rows[0], *provenance])
        writer.writeheader()
        writer.writerows(dict(row, **provenance) for row in rows)
    summary = {
        "bank_rows": len(parsed.records),
        "with_bic": sum(r.bic is not None for r in parsed.records),
        "bundle_sha256": sha256(encoded),
        "statuses": {},
    }
    for row in rows:
        summary["statuses"][row["status"]] = summary["statuses"].get(row["status"], 0) + 1
    with (args.output / "summary.json").open("x") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
