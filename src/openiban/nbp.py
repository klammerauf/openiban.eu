"""Live EWIB lookup. Only the eight-digit clearing code leaves this service."""

import json
import re
from http.client import HTTPException
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://ewib.nbp.pl/api/v1/zapytanie1/"
MAX_RESPONSE_BYTES = 1_048_576


class NBPUnavailable(Exception):
    """Transport failure or an untrustworthy EWIB response."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _text(value):
    if not isinstance(value, str):
        raise ValueError("Expected string")
    return value.strip()


def parse_response(content: bytes, code: str) -> dict | None:
    """Match the full clearing code, including units; reject ambiguous records."""
    try:
        data = json.loads(content, object_pairs_hook=_object)
        owners = data["listaWlascicieli"]
        if not isinstance(owners, list):
            raise ValueError("Expected owner list")
        matches = []
        for owner in owners:
            name = _text(owner["nazwa"])
            if not name:
                raise ValueError("Missing institution name")
            units = owner.get("jednostki", [])
            if not isinstance(units, list):
                raise ValueError("Expected units list")
            if owner.get("siedziba") is not None:
                units = [owner["siedziba"], *units]
            for unit in units:
                entries = unit.get("numeryRozliczeniowe", [])
                if not isinstance(entries, list):
                    raise ValueError("Expected clearing codes")
                for entry in entries:
                    number = _text(entry["numer"])
                    if not re.fullmatch(r"[0-9]{8}", number):
                        raise ValueError("Invalid clearing code")
                    if number != code:
                        continue
                    bics = {"BIC": set(), "BIC SEPA": set()}
                    identifiers = entry.get("numeryBic", [])
                    if not isinstance(identifiers, list):
                        raise ValueError("Expected BIC list")
                    for identifier in identifiers:
                        label = _text(identifier["nazwa"])
                        if label not in bics:
                            continue
                        value = _text(identifier["numer"])
                        if not value:
                            continue
                        if not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", value):
                            raise ValueError("Invalid BIC")
                        bics[label].add(value)
                    if any(len(values) > 1 for values in bics.values()):
                        raise ValueError("Ambiguous BIC")
                    matches.append(
                        {
                            "bank_code": code,
                            "name": name,
                            "postal_code": _text(unit.get("kodPocztowy", "")),
                            "city": _text(unit.get("miejscowosc", "")),
                            "bic": next(iter(bics["BIC"]), None),
                            "bic_sepa": next(iter(bics["BIC SEPA"]), None),
                            "deletion_announced": False,
                            "successor_bank_code": None,
                        }
                    )
        if matches:
            if any(match != matches[0] for match in matches[1:]):
                raise ValueError("Ambiguous clearing code")
            return matches[0]
        # A nonempty response without the requested code is not evidence of absence.
        if owners:
            raise ValueError("Requested code absent from nonempty response")
        return None
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise NBPUnavailable("Invalid EWIB response") from exc


class NBPClient:
    def lookup(self, code: str) -> dict | None:
        if not re.fullmatch(r"[0-9]{8}", code):
            raise ValueError("Expected eight-digit clearing code")
        request = Request(
            f"{ENDPOINT}?nrRozliczeniowy={code}&format=json",
            headers={"Accept": "application/json", "User-Agent": "OpenIBAN.eu/0.1"},
        )
        try:
            # No redirects, retries or persistence of responses/account identifiers.
            with build_opener(NoRedirects()).open(request, timeout=5) as response:
                if response.status != 200:
                    raise NBPUnavailable("Unexpected EWIB status")
                if response.headers.get_content_type() != "application/json":
                    raise NBPUnavailable("Unexpected EWIB content type")
                content = response.read(MAX_RESPONSE_BYTES + 1)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise NBPUnavailable("EWIB response too large")
        except (URLError, OSError, ValueError, HTTPException) as exc:
            raise NBPUnavailable("EWIB request failed") from exc
        return parse_response(content, code)
