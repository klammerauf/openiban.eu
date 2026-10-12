"""Synthetic fixtures using the observed BdE schema; no publisher data in Git."""

import csv
import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from openiban.api import create_app
from openiban.directories import ES_HEADERS, SOURCES, parse_directory
from openiban.directory_storage import (
    activate_directory,
    active,
    history,
    list_directory_versions,
    lookup_directory,
    records,
    stage_directory,
    versions,
)
from openiban.storage import initialize, lookup, today
from openiban.validation import validate_iban
from tests.test_directories import iban


def source(rows=None, padding=True):
    if rows is None:
        rows = [
            [
                "ES0224",
                "",
                "Synthetic Bank, S.A.",
                "Entidad de crédito",
                "Address",
                "No",
                "",
                "0073",
            ],
            ["ESA06302657", "", "Synthetic Other Bank", "Entidad de crédito", "", "Sí", "", "0244"],
            ["ES8620", "", "Finance Company", "Otra institución", "", "No", "", "8620"],
            ["ES9000", "", "Central Bank", "Banco central", "", "Sí", "", "9000"],
            [
                "ESV63050835",
                "",
                "Money Fund",
                "Fondo del mercado monetario",
                "",
                "No",
                "",
                "FI2680",
            ],
        ]
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(ES_HEADERS)
    writer.writerows(rows)
    value = output.getvalue()
    if padding:
        value = value.replace("\r\n", "    \r\n")
    return value.encode("utf-8-sig")


def stage(engine, tmp_path, content=None, start=None, end=None):
    path = tmp_path / "es.csv"
    path.write_bytes(source() if content is None else content)
    return stage_directory(
        engine,
        "ES",
        path,
        start or today(),
        end or today() + timedelta(days=30),
        SOURCES["ES"].download,
    )


def test_observed_schema_uses_supervisor_and_filters_categories():
    result = parse_directory("ES", source())
    assert result.total_rows == 5 and result.ignored_rows == 3
    assert [r.bank_code for r in result.records] == ["0073", "0244"]
    assert all(r.bic is None and not r.city and not r.postal_code for r in result.records)
    assert result.records[0].name == "Synthetic Bank, S.A."
    assert parse_directory("ES", source(padding=False)) == result


@pytest.mark.parametrize(
    "old,new",
    [
        ("CÓDIGO DE SUPERVISOR", "BIC"),
        ('"0073"', '"73"'),
        ('"0244"', '"0073"'),
        ('"Entidad de crédito"', '"Payment institution"'),
        ('"No"', '"Unknown"'),
        ('"Synthetic Bank, S.A."', '"=HYPERLINK(1)"'),
        ('"Synthetic Bank, S.A."', '"\tSynthetic Bank"'),
        ('"ES0224"', '"DE0224"'),
        ('"FI2680"', '"2680"'),
        ('"0073"', '"0073","extra"'),
        ('"0073"', '"0073'),
        ('"0073"', '"007\x003"'),
        ('"Synthetic Bank, S.A."', '"Synthetic\nBank"'),
        ('"0073"', '"007A"'),
    ],
)
def test_schema_drift_malformed_and_ambiguous_csv_fail(old, new):
    value = source().decode("utf-8-sig").replace(old, new).encode()
    with pytest.raises(ValueError):
        parse_directory("ES", value)


def test_no_credit_institutions_and_row_limit_fail(monkeypatch):
    with pytest.raises(ValueError):
        parse_directory(
            "ES", source().replace("Entidad de crédito".encode(), b"Otra instituci\xc3\xb3n")
        )
    monkeypatch.setattr("openiban.directories.MAX_ROWS", 2)
    with pytest.raises(ValueError):
        parse_directory("ES", source())
    with pytest.raises(ValueError):
        parse_directory("ES", source() + b"\xff")


@pytest.mark.parametrize(
    "value,reason",
    [
        ("ES9121000418450200051332", "valid"),
        (" es91 2100 0418 4502 0005 1332 ", "valid"),
        ("ES9121000418450200051333", "invalid_checksum"),
        ("ES0021000418450200051332", "invalid_checksum"),
        ("ES9921000418450200051332", "invalid_checksum"),
        ("ES912100041845020005133", "invalid_format"),
        ("ES91210004184502000513322", "invalid_format"),
        ("ES912100041845020005133A", "invalid_format"),
        ("ES91-21000418450200051332", "invalid_format"),
        ("ES９121000418450200051332", "invalid_characters"),
    ],
)
def test_es_format_and_mod97(value, reason):
    assert validate_iban(value).reason == reason


def test_api_evidence_is_separate_and_no_bic_is_invented(engine, tmp_path):
    version = stage(engine, tmp_path)["version"]
    known = iban("ES", "0073" + "0" * 16)
    with TestClient(create_app(engine)) as client:

        def check(value):
            response = client.post("/v1/validate", json={"iban": value})
            assert response.status_code == 200
            return response.json()

        assert check(known)["bank_lookup_status"] == "unavailable"
        activate_directory(engine, "ES", version, review_note="Synthetic review")
        result = check(known)
        assert result["iban_valid"] and result["bank_code_valid"]
        assert result["bank"]["bank_code"] == "0073" and result["bank"]["bic"] is None
        assert result["data"]["version"] == version
        # Excluded categories and European ID are not usable lookup keys.
        for code in ["0224", "8620", "9000", "9999"]:
            result = check(iban("ES", code + "0" * 16))
            assert result["iban_valid"] is True
            assert result["bank_code_valid"] is False
            assert result["bank_lookup_status"] == "not_found" and result["bank"] is None
        result = check(known[:-1] + "1")
        assert result["iban_valid"] is False and result["bank_lookup_status"] == "not_checked"
        assert result["bank_code_valid"] is None
        countries = client.get("/v1/countries").json()["countries"]
        assert {"code": "ES", "iban_length": 24, "bank_lookup_supported": True} in countries


def test_es_rollback_expiry_future_and_failed_import(engine, tmp_path, import_file):
    german = import_file(make_active=True)
    first = stage(engine, tmp_path)["version"]
    activate_directory(engine, "ES", first, review_note="First")
    second = stage(engine, tmp_path, source().replace(b"Synthetic", b"Updated"))["version"]
    assert lookup_directory(engine, "ES", "0073")[0]["version"] == first
    activate_directory(engine, "ES", second, review_note="Second")
    with pytest.raises(ValueError):
        activate_directory(engine, "ES", first, review_note="Rollback", expected_previous_id=first)
    activate_directory(engine, "ES", first, review_note="Rollback", expected_previous_id=second)
    with pytest.raises(ValueError):
        stage(engine, tmp_path, b"broken")
    assert len(list_directory_versions(engine, "ES")) == 2
    assert lookup_directory(engine, "ES", "0073")[0]["version"] == first
    expired = stage(
        engine,
        tmp_path,
        source().replace(b"Synthetic", b"Expired"),
        today() - timedelta(days=2),
        today() - timedelta(days=1),
    )["version"]
    with pytest.raises(ValueError):
        activate_directory(engine, "ES", expired, review_note="Expired")
    activate_directory(engine, "ES", expired, review_note="Explicit rollback", allow_expired=True)
    with TestClient(create_app(engine)) as client:
        result = client.post("/v1/validate", json={"iban": iban("ES", "0073" + "0" * 16)}).json()
        assert result["iban_valid"] and result["bank_lookup_status"] == "stale"
        assert result["bank_code_valid"] is None and result["bank"] is None
    future = stage(
        engine,
        tmp_path,
        source().replace(b"Synthetic", b"Future"),
        today() + timedelta(days=1),
        today() + timedelta(days=2),
    )["version"]
    with pytest.raises(ValueError):
        activate_directory(engine, "ES", future, review_note="Future")
    assert lookup(engine, "12345678")[0]["version"] == german["version"]


def test_legacy_de_migration_is_additive_repeatable_and_keeps_data(engine, import_file, tmp_path):
    import_file(make_active=True)
    before = lookup(engine, "12345678")
    # Emulate the original DE-only schema with its live pointer and history.
    for table in [history, active, records, versions]:
        table.drop(engine)
    initialize(engine)
    initialize(engine)
    assert lookup(engine, "12345678") == before
    with engine.connect() as conn:
        assert (
            conn.execute(select(active.c.dataset_id).where(active.c.country == "ES")).scalar_one()
            is None
        )
    version = stage(engine, tmp_path)["version"]
    activate_directory(engine, "ES", version, review_note="Reviewed")
    initialize(engine)
    assert lookup_directory(engine, "ES", "0073")[0]["version"] == version
    assert lookup(engine, "12345678") == before
