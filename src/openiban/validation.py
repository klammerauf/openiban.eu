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


def validate_iban(raw: str) -> Validation:
    """DE and PL country format plus MOD-97; no domestic account verification."""
    compact = "".join(raw.split())
    if not compact.isascii() or not compact.upper().startswith("PL"):
        return validate_german_iban(raw)
    normalized = compact.upper()
    if not re.fullmatch(r"PL[0-9]{26}", normalized):
        return Validation(normalized, True, False, None, False, "invalid_format")
    # PL -> P=25, L=21. Reject noncanonical check digits 00, 01 and 99.
    digits = normalized[4:] + "2521" + normalized[2:4]
    valid = 2 <= int(normalized[2:4]) <= 98 and int(digits) % 97 == 1
    return Validation(
        normalized, True, True, valid, valid, "valid" if valid else "invalid_checksum"
    )
