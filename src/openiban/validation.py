"""Pure German IBAN syntax and ISO 7064 MOD-97-10 check.

This does not check domestic account-number algorithms or account existence.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Validation:
    normalized: str
    country_supported: bool
    format_valid: bool | None
    checksum_valid: bool | None
    iban_valid: bool | None
    reason: str


def validate_german_iban(raw: str) -> Validation:
    # Remove whitespace only. Do not discard letters, punctuation, or silently
    # transliterate non-ASCII characters into a different account identifier.
    compact = "".join(raw.split())
    if not compact.isascii():
        return Validation(compact, False, False, None, False, "invalid_characters")
    normalized = compact.upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", normalized):
        return Validation(
            normalized, normalized.startswith("DE"), False, None, False, "invalid_format"
        )
    if not normalized.startswith("DE"):
        return Validation(normalized, False, None, None, None, "unsupported_country")
    if not re.fullmatch(r"DE[0-9]{20}", normalized):
        return Validation(normalized, True, False, None, False, "invalid_format")
    # DE -> D=13, E=14. Canonical check digits must be between 02 and 98.
    rearranged = normalized[4:] + "1314" + normalized[2:4]
    valid = 2 <= int(normalized[2:4]) <= 98 and int(rearranged) % 97 == 1
    return Validation(
        normalized, True, True, valid, valid, "valid" if valid else "invalid_checksum"
    )


# BBAN layouts from the SWIFT IBAN Registry and official country pages.
COUNTRIES = {
    "DE": (22, r"[0-9]{18}", 8),
    "CH": (21, r"[0-9]{5}[A-Z0-9]{12}", 5),
    "PL": (28, r"[0-9]{24}", 8),
    "LT": (20, r"[0-9]{16}", 5),
    "BE": (16, r"[0-9]{12}", 3),
    "CZ": (24, r"[0-9]{20}", 4),
    "LV": (21, r"[A-Z]{4}[A-Z0-9]{13}", 4),
    "SI": (19, r"[0-9]{15}", 5),
    "GR": (27, r"[0-9]{7}[A-Z0-9]{16}", 3),
    "NL": (18, r"[A-Z]{4}[0-9]{10}", 4),
}


def validate_iban(raw: str) -> Validation:
    compact = "".join(raw.split())
    if not compact.isascii():
        return Validation(compact, False, False, None, False, "invalid_characters")
    normalized = compact.upper()
    country = normalized[:2]
    if country == "DE":
        return validate_german_iban(raw)
    supported = country in COUNTRIES
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", normalized):
        return Validation(normalized, supported, False, None, False, "invalid_format")
    if not supported:
        return Validation(normalized, False, None, None, None, "unsupported_country")
    _, pattern, _ = COUNTRIES[country]
    if not re.fullmatch(country + r"[0-9]{2}" + pattern, normalized):
        return Validation(normalized, True, False, None, False, "invalid_format")
    rearranged = normalized[4:] + normalized[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    valid = 2 <= int(normalized[2:4]) <= 98 and int(digits) % 97 == 1
    return Validation(
        normalized, True, True, valid, valid, "valid" if valid else "invalid_checksum"
    )
