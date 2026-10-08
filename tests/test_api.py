from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from openiban.api import create_app
from openiban.storage import activate, build_engine, today
from tests.conftest import bank_line, iban_for


def test_known_bank(engine, import_file):
    imported = import_file(make_active=True)
    with TestClient(create_app(engine)) as client:
        response = client.post("/v1/validate", json={"iban": iban_for()})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["iban_valid"] is True
        assert data["checks"] == {"format": True, "checksum": True}
        assert data["bank_lookup_status"] == "found"
        assert data["bank_code_valid"] is True
        assert data["bank"]["bic"] == "TESTDEFFXXX"
        assert data["data"]["version"] == imported["version"]
        assert data["data"]["source"] == "Source: Deutsche Bundesbank"
        assert client.get("/health/ready").status_code == 200


def test_unknown_and_deleted_bank_are_distinct(engine, import_file):
    content = bank_line() + b"\n" + bank_line(code="87654321", flag="D", record_id="000002")
    import_file(content, make_active=True)
    with TestClient(create_app(engine)) as client:
        for code, status in [("99999999", "not_found"), ("87654321", "deleted")]:
            result = client.post("/v1/validate", json={"iban": iban_for(code)}).json()
            assert result["iban_valid"] is True
            assert result["bank_lookup_status"] == status
            assert result["bank_code_valid"] is False
            assert result["bank"] is None


def test_invalid_checksum_does_not_return_bank(engine, import_file):
    import_file(make_active=True)
    with TestClient(create_app(engine)) as client:
        result = client.post("/v1/validate", json={"iban": "DE59123456780123456789"}).json()
    assert result["iban_valid"] is False
    assert result["bank_lookup_status"] == "not_checked"
    assert result["bank"] is None


def test_unsupported_country_is_explicit(engine):
    with TestClient(create_app(engine)) as client:
        result = client.post("/v1/validate", json={"iban": "GB82WEST12345698765432"}).json()
    assert result["iban_valid"] is None
    assert result["country_supported"] is False
    assert result["reason"] == "unsupported_country"


def test_empty_dataset_and_missing_schema_preserve_syntax_result(engine, tmp_path):
    missing_schema = build_engine(f"sqlite:///{tmp_path / 'uninitialized.db'}")
    for database in [engine, missing_schema]:
        with TestClient(create_app(database)) as client:
            result = client.post("/v1/validate", json={"iban": iban_for()}).json()
            assert result["iban_valid"] is True
            assert result["bank_lookup_status"] == "unavailable"
            assert result["bank_code_valid"] is None
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 503
    missing_schema.dispose()


def test_stale_data_is_not_reported_as_unknown_bank(engine, import_file):
    result = import_file(start=today() - timedelta(days=5), end=today() - timedelta(days=1))
    activate(engine, result["version"], allow_expired=True)
    with TestClient(create_app(engine)) as client:
        result = client.post("/v1/validate", json={"iban": iban_for()}).json()
        assert result["iban_valid"] is True
        assert result["bank_lookup_status"] == "stale"
        assert result["bank_code_valid"] is None
        assert result["bank"] is None
        assert result["data"]["status"] == "expired"
        assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"iban": 123},
        {"iban": None},
        {"iban": ""},
        {"iban": "x" * 129},
        {"iban": iban_for(), "extra": "secret"},
    ],
)
def test_invalid_requests_do_not_echo_input(engine, payload):
    with TestClient(create_app(engine)) as client:
        response = client.post("/v1/validate", json=payload)
        assert response.status_code == 422
        assert "input" not in response.json()
        assert iban_for() not in response.text
        assert "secret" not in response.text


def test_malformed_and_large_requests(engine):
    with TestClient(create_app(engine)) as client:
        response = client.post(
            "/v1/validate",
            content='{"iban":"SECRET",',
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        assert "SECRET" not in response.text
        assert client.post("/v1/validate", content=b"x" * 4097).status_code == 413
        assert (
            client.post("/v1/validate", content=iter([b"x" * 3000, b"y" * 3000])).status_code == 413
        )


def test_query_parameters_are_rejected_and_docs_work(engine):
    with TestClient(create_app(engine)) as client:
        response = client.post("/v1/validate?iban=SECRET", json={"iban": iban_for()})
        assert response.status_code == 400
        assert "SECRET" not in response.text
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert "/v1/validate" in schema["paths"]
        assert client.get("/v1/countries").json()["countries"][0]["code"] == "DE"
