"""Parser for the public Bundesbank fixed-width TXT (168 bytes per row)."""

import re
from dataclasses import dataclass

SOURCE_URL = (
    "https://www.bundesbank.de/de/aufgaben/unbarer-zahlungsverkehr/"
    "serviceangebot/bankleitzahlen/download-bankleitzahlen-602592"
)
ATTRIBUTION = "Quelle: Deutsche Bundesbank"
MAX_FILE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class BankRecord:
    bank_code: str
    name: str
    postal_code: str
    city: str
    bic: str | None
    record_number: str
    change_flag: str
    deletion_announced: bool
    successor_bank_code: str | None


@dataclass(frozen=True)
class ParsedFile:
    records: list[BankRecord]
    total_rows: int
    ignored_branch_rows: int


def parse_txt(content: bytes) -> ParsedFile:
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("Datei ist leer oder größer als 20 MiB.")
    records = []
    seen_ids: set[str] = set()
    seen_codes: set[str] = set()
    branch_rows = 0
    # Split bytes before decoding: Latin-1 is a one-byte encoding. Do not strip
    # fixed-width padding or accept blank rows/truncated exports silently.
    lines = content.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    for number, raw in enumerate(lines, start=1):
        raw = raw.removesuffix(b"\r")
        if len(raw) != 168:
            raise ValueError(f"Zeile {number}: erwartet werden genau 168 Bytes (öffentliche TXT).")
        line = raw.decode("latin-1")
        if any(ord(char) < 32 or 127 <= ord(char) < 160 for char in line):
            raise ValueError(f"Zeile {number}: unerlaubtes Steuerzeichen/Encoding.")
        code, leader = line[:8], line[8]
        record_id, flag = line[152:158], line[158]
        successor = line[160:168]
        bic = line[139:150].strip() or None
        if (
            not re.fullmatch(r"[0-9]{8}", code)
            or leader not in {"1", "2"}
            or flag not in {"A", "M", "U", "D"}
            or line[159] not in {"0", "1"}
            or not re.fullmatch(r"[0-9]{6}", record_id)
            or not re.fullmatch(r"[0-9]{8}", successor)
            or not re.fullmatch(r"[0-9]{5}", line[67:72])
            or not line[9:67].strip()
            or not line[72:107].strip()
            or (
                bic is not None
                and not re.fullmatch(r"[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", bic)
            )
        ):
            raise ValueError(f"Zeile {number}: ungültige Felder im Bundesbank-Datensatz.")
        if record_id in seen_ids:
            raise ValueError(f"Zeile {number}: doppelte Datensatznummer.")
        seen_ids.add(record_id)
        if leader == "2":
            branch_rows += 1
            continue
        if code in seen_codes:
            raise ValueError(f"Zeile {number}: doppelte bankleitzahlführende BLZ.")
        seen_codes.add(code)
        records.append(
            BankRecord(
                bank_code=code,
                name=line[9:67].rstrip(),
                postal_code=line[67:72],
                city=line[72:107].rstrip(),
                bic=bic,
                record_number=record_id,
                change_flag=flag,
                deletion_announced=line[159] == "1",
                successor_bank_code=None if successor == "00000000" else successor,
            )
        )
    if not records or not any(record.change_flag != "D" for record in records):
        raise ValueError("Datei enthält keine aktiven bankleitzahlführenden Datensätze.")
    return ParsedFile(records, len(lines), branch_rows)
