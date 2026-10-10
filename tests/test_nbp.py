import copy
import json
from email.message import Message
from http.client import IncompleteRead
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from openiban.api import create_app
from openiban.nbp import MAX_RESPONSE_BYTES, NBPClient, NBPUnavailable, parse_response
from openiban.validation import validate_iban

CODE = "10100000"
# Synthetic account with a calculated MOD-97 checksum, not an existing account.
IBAN = "PL" + str(98 - int(CODE + "0" * 16 + "252100") % 97).zfill(2) + CODE + "0" * 16


def payload():
    return {
        "listaWlascicieli": [
            {
                "nazwa": "Synthetic Polish Bank",
                "siedziba": {
                    "miejscowosc": "Warszawa",
                    "kodPocztowy": "00-000",
                    "numeryRozliczeniowe": [
                        {
                            "numer": CODE,
                            "numeryBic": [
                                {"nazwa": "BIC", "numer": "TESTPLPWXXX"},
                                {"nazwa": "BIC SEPA", "numer": "TESTPLP1XXX"},
                                {"nazwa": "BIC TARGET", "numer": "OTHER"},
                            ],
                        }
                    ],
                },
            }
        ]
    }


def encode(data):
    return json.dumps(data).encode()


@pytest.mark.parametrize("unit", [False, True])
def test_head_office_and_units(unit):
    data = payload()
    if unit:
        owner = data["listaWlascicieli"][0]
        owner["jednostki"] = [owner.pop("siedziba")]
    bank = parse_response(encode(data), CODE)
    assert bank["name"] == "Synthetic Polish Bank"
    assert bank["bank_code"] == CODE
    assert bank["bic"] == "TESTPLPWXXX"
    assert bank["bic_sepa"] == "TESTPLP1XXX"
    assert bank["city"] == "Warszawa"


def test_empty_and_missing_bics():
    assert parse_response(b'{"listaWlascicieli":[]}', CODE) is None
    data = payload()
    entry = data["listaWlascicieli"][0]["siedziba"]["numeryRozliczeniowe"][0]
    entry["numeryBic"] = [{"nazwa": "BIC SEPA", "numer": "TESTPLPW"}]
    bank = parse_response(encode(data), CODE)
    assert bank["bic"] is None
    assert bank["bic_sepa"] == "TESTPLPW"


@pytest.mark.parametrize(
    "content",
    [
        b"<html>Error</html>",
        b"{}",
        b"null",
        b'{"listaWlascicieli":null}',
        b'{"listaWlascicieli":[],"listaWlascicieli":[]}',
        b"\xff",
        b'{"listaWlascicieli":[{}]}',
    ],
)
def test_invalid_schema(content):
    with pytest.raises(NBPUnavailable):
        parse_response(content, CODE)


def test_wrong_code_and_conflicting_records():
    data = payload()
    with pytest.raises(NBPUnavailable):
        parse_response(encode(data), "10100001")
    other = copy.deepcopy(data["listaWlascicieli"][0])
    other["nazwa"] = "Different bank"
    data["listaWlascicieli"].append(other)
    with pytest.raises(NBPUnavailable):
        parse_response(encode(data), CODE)


@pytest.mark.parametrize("value", ["bad", 123, None])
def test_invalid_bic(value):
    data = payload()
    data["listaWlascicieli"][0]["siedziba"]["numeryRozliczeniowe"][0]["numeryBic"][0]["numer"] = (
        value
    )
    with pytest.raises(NBPUnavailable):
        parse_response(encode(data), CODE)


def mock_transport(monkeypatch, content, content_type="application/json"):
    response = MagicMock()
    response.status = 200
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    response.read.return_value = content
    response.__enter__.return_value = response
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr("openiban.nbp.build_opener", lambda *args: opener)
    return opener, response


def test_transport_sends_only_code_and_has_timeout(monkeypatch):
    opener, response = mock_transport(monkeypatch, encode(payload()))
    assert NBPClient().lookup(CODE)["bic"] == "TESTPLPWXXX"
    request = opener.open.call_args.args[0]
    assert request.full_url == (
        "https://ewib.nbp.pl/api/v1/zapytanie1/?nrRozliczeniowy=10100000&format=json"
    )
    assert IBAN not in request.full_url
    assert request.data is None
    assert opener.open.call_args.kwargs == {"timeout": 5}
    response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)


@pytest.mark.parametrize(
    "error",
    [
        URLError("dns"),
        TimeoutError(),
        HTTPError("url", 429, "limited", {}, None),
        HTTPError("url", 503, "down", {}, None),
        IncompleteRead(b"partial"),
    ],
)
def test_transport_errors(monkeypatch, error):
    opener, _ = mock_transport(monkeypatch, b"")
    opener.open.side_effect = error
    with pytest.raises(NBPUnavailable):
        NBPClient().lookup(CODE)


@pytest.mark.parametrize(
    "content,content_type",
    [
        (b"x" * (MAX_RESPONSE_BYTES + 1), "application/json"),
        (b"<html>Error</html>", "text/html"),
    ],
)
def test_response_boundaries(monkeypatch, content, content_type):
    mock_transport(monkeypatch, content, content_type)
    with pytest.raises(NBPUnavailable):
        NBPClient().lookup(CODE)


@pytest.mark.parametrize("raw", [IBAN, IBAN.lower(), " ".join([IBAN[:4], IBAN[4:]])])
def test_polish_validation(raw):
    assert validate_iban(raw).iban_valid is True


@pytest.mark.parametrize(
    "raw,reason",
    [
        ("PL00" + IBAN[4:], "invalid_checksum"),
        (IBAN[:-1], "invalid_format"),
        (IBAN + "0", "invalid_format"),
        (IBAN[:4] + "A" + IBAN[5:], "invalid_format"),
        (IBAN.replace("0", "０"), "invalid_characters"),
    ],
)
def test_invalid_polish_validation(raw, reason):
    assert validate_iban(raw).reason == reason


@pytest.mark.parametrize("status", ["found", "not_found", "unavailable"])
def test_api_live_lookup_without_dataset(engine, status):
    nbp = MagicMock(spec=NBPClient)
    nbp.lookup.return_value = parse_response(encode(payload()), CODE) if status == "found" else None
    if status == "unavailable":
        nbp.lookup.side_effect = NBPUnavailable()
    with TestClient(create_app(engine, nbp_client=nbp)) as client:
        result = client.post("/v1/validate", json={"iban": IBAN}).json()
    nbp.lookup.assert_called_once_with(CODE)
    assert result["iban_valid"] is True
    assert result["bank_lookup_status"] == status
    assert (
        result["bank_code_valid"]
        == {"found": True, "not_found": False, "unavailable": None}[status]
    )
    assert result["data"] is None
    assert "Narodowy Bank Polski" in result["lookup_source"]
    if status == "found":
        assert result["bank"]["bic_sepa"] == "TESTPLP1XXX"


def test_invalid_and_non_polish_iban_do_not_call_nbp(engine):
    nbp = MagicMock(spec=NBPClient)
    with TestClient(create_app(engine, nbp_client=nbp)) as client:
        for iban in [
            "PL00" + IBAN[4:],
            "PL123",
            "GB82WEST12345698765432",
            "DE58123456780123456789",
        ]:
            client.post("/v1/validate", json={"iban": iban})
        assert client.get("/v1/countries").json()["countries"][1]["code"] == "PL"
    nbp.lookup.assert_not_called()
