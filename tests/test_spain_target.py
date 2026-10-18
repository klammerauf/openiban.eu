"""Synthetic TARGET records; no publisher data in Git."""

import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from openiban.api import create_app
from openiban.directories import SOURCES, parse_directory
from openiban.directory_storage import activate_directory, list_directory_versions, stage_directory
from openiban.spain_target import (
    FOOTNOTE,
    SCHEMA,
    TARGET_URL,
    parse_bundle,
    reconcile,
    sha256,
    target_rows,
)
from openiban.storage import lookup, today
from tests.test_directories import iban
from tests.test_spain import source


def page(rows, number=1):
    return (
        "PARTICIPANTES TITULARES CUENTA DCA RTGS\n"
        "EN TARGET - BANCO DE ESPAÑA\nBIC 11   DENOMINACIÓN   NRBE\n"
        + "\n".join(rows)
        + "\n"
        + FOOTNOTE
        + f"\n{number}\n\f"
    )


def bundle():
    mfi = source()
    value = page(
        [
            "TESTESMM045 Synthetic Bank, S.A. 0073",
            "* Synthetic Other Bank 0244",
            "OTHEESMMXXX Synthetic Nonbank 9090",
        ]
    )
    return dict(
        schema=SCHEMA,
        mfi_csv=mfi.decode("utf-8"),
        target_text=value,
        name_reviews=[],
        blocked=[],
        provenance=dict(
            target_url=TARGET_URL,
            mfi_url=SOURCES["ES"].download,
            mfi_sha256=sha256(mfi),
            target_text_sha256=sha256(value.encode()),
            target_pdf_sha256="a" * 64,
            retrieved_on="2026-10-18",
        ),
    )


def encoded(value=None):
    return json.dumps(bundle() if value is None else value).encode()


def test_enrichment_withholding_scope_and_complete_pages():
    result = parse_directory("ES", encoded())
    assert result.total_rows == 5 and result.ignored_rows == 3
    assert [(r.bank_code, r.bic) for r in result.records] == [
        ("0073", "TESTESMM045"),
        ("0244", None),
    ]
    _, rows = reconcile(source(), bundle()["target_text"], [], [])
    assert [r["status"] for r in rows] == ["matched", "not_published", "outside_mfi_credit_scope"]
    result, rows = reconcile(
        source(),
        page(["TESTESMM045 Synthetic Bank, S.A. 0073"])
        + page(["OTHEESMMXXX Synthetic Nonbank 9090"], 2),
        [],
        [],
    )
    assert len(result.records) == 2 and rows[1]["status"] == "not_in_target"


@pytest.mark.parametrize(
    "old,new",
    [
        ("TESTESMM045", "TESTESMM"),
        ("TESTESMM045", "TESTDEMM045"),
        ("TESTESMM045", "testESMM045"),
        ("0073", "073"),
        ("DENOMINACIÓN", "NAME"),
        ("\n1\n", "\n2\n"),
        (FOOTNOTE, ""),
        ("Synthetic Bank, S.A. 0073", "Synthetic\nBank, S.A. 0073"),
        ("* Synthetic Other Bank 0244", "* Synthetic Other Bank 0073"),
        ("OTHEESMMXXX", "TESTESMM045"),
    ],
)
def test_corrupt_schema_duplicate_code_or_bic_fail(old, new):
    with pytest.raises(ValueError):
        target_rows(bundle()["target_text"].replace(old, new))


def test_name_review_and_conflict_decisions_are_bound_to_both_names_and_bic():
    value = bundle()["target_text"].replace("Synthetic Bank, S.A.", "Synthetic Bank S.E.")
    directory, rows = reconcile(source(), value, [], [])
    assert directory.records[0].bic is None and rows[0]["status"] == "name_review_required"
    decision = dict(
        nrbe="0073",
        target_name="Synthetic Bank S.E.",
        mfi_name="Synthetic Bank, S.A.",
        bic11="TESTESMM045",
        reason="Reviewed expansion",
    )
    assert reconcile(source(), value, [decision], [])[0].records[0].bic == "TESTESMM045"
    assert reconcile(source(), value, [], [decision])[0].records[0].bic is None
    for key in decision:
        with pytest.raises(ValueError):
            reconcile(source(), value, [dict(decision, **{key: ""})], [])
    with pytest.raises(ValueError):
        reconcile(source(), value, [decision], [decision])


@pytest.mark.parametrize(
    "field",
    [
        "mfi_sha256",
        "target_pdf_sha256",
        "target_text_sha256",
        "target_url",
        "mfi_url",
        "retrieved_on",
    ],
)
def test_provenance_validation(field):
    value = bundle()
    value["provenance"][field] = "invalid"
    with pytest.raises(ValueError):
        parse_bundle(encoded(value))


def test_duplicate_keys_and_nested_bundles_fail():
    with pytest.raises(ValueError):
        parse_bundle(encoded().replace(b'"schema":', b'"schema":"other", "schema":'))
    value = bundle()
    value["mfi_csv"] = encoded().decode()
    value["provenance"]["mfi_sha256"] = sha256(value["mfi_csv"].encode())
    with pytest.raises(ValueError):
        parse_bundle(encoded(value))


def test_staging_api_idempotency_and_failed_import_preserve_active_data(
    engine, tmp_path, import_file
):
    import_file(make_active=True)
    german_before = lookup(engine, "12345678")
    path = tmp_path / "bundle.json"
    path.write_bytes(encoded())
    start, end = today(), today() + timedelta(days=30)
    first = stage_directory(engine, "ES", path, start, end, TARGET_URL)
    assert first["sha256"] == sha256(encoded())
    assert stage_directory(engine, "ES", path, start, end, TARGET_URL)["already_imported"]
    with TestClient(create_app(engine)) as client:

        def check():
            return client.post("/v1/validate", json={"iban": iban("ES", "0073" + "0" * 16)}).json()

        assert check()["bank_lookup_status"] == "unavailable"
        activate_directory(engine, "ES", first["version"], review_note="Synthetic review")
        assert check()["bank"]["bic"] == "TESTESMM045"
        assert check()["data"]["source_url"] == TARGET_URL
        other = bundle()
        other["target_text"] = other["target_text"].replace("TESTESMM045", "TESTESMMXXX")
        other["provenance"]["target_text_sha256"] = sha256(other["target_text"].encode())
        path.write_bytes(encoded(other))
        second = stage_directory(engine, "ES", path, start, end, TARGET_URL)
        assert second["version"] != first["version"]
        assert check()["bank"]["bic"] == "TESTESMM045"
        with pytest.raises(ValueError):
            stage_directory(engine, "ES", path, start, end, SOURCES["ES"].download)
        path.write_bytes(b'{"schema":"broken"}')
        with pytest.raises(ValueError):
            stage_directory(engine, "ES", path, start, end, TARGET_URL)
        assert len(list_directory_versions(engine, "ES")) == 2
        assert check()["data"]["version"] == first["version"]
    assert lookup(engine, "12345678") == german_before
