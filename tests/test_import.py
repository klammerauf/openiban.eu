from datetime import timedelta

import pytest
from sqlalchemy import select

from openiban.bundesbank import parse_txt
from openiban.storage import activate, activations, list_versions, lookup, today
from tests.conftest import bank_line


def test_parse_umlauts_and_ignore_deleted_branch():
    data = bank_line() + b"\r\n" + bank_line(leader="2", flag="D", record_id="000002") + b"\r\n"
    parsed = parse_txt(data)
    assert parsed.total_rows == 2
    assert parsed.ignored_branch_rows == 1
    assert len(parsed.records) == 1
    assert parsed.records[0].name == "Musterbank München"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<html>download error</html>",
        bank_line()[:-1],
        bank_line() + b"x",
        bank_line() + b"\n\n",
        bank_line(flag="X"),
        bank_line(leader="3"),
        bank_line(code="1234567X"),
        bank_line(deletion="2"),
        bank_line(bic="BAD"),
        bank_line() + b"\n" + bank_line(),
        bank_line() + b"\n" + bank_line(record_id="000002"),
        bank_line(flag="D"),
        bank_line(leader="2"),
    ],
)
def test_reject_malformed_imports(data):
    with pytest.raises(ValueError):
        parse_txt(data)


def test_stage_idempotency_activation_and_rollback(engine, import_file):
    first = import_file()
    assert lookup(engine, "12345678") == (None, None)
    repeated = import_file()
    assert repeated["already_imported"] is True
    assert repeated["version"] == first["version"]
    activate(engine, first["version"])
    assert lookup(engine, "12345678")[1]["name"] == "Musterbank München"
    second = import_file(bank_line(name="Neue Musterbank") + b"\n")
    assert second["changed"] == 1
    assert lookup(engine, "12345678")[1]["name"] == "Musterbank München"
    activate(engine, second["version"])
    assert lookup(engine, "12345678")[1]["name"] == "Neue Musterbank"
    activate(engine, first["version"])
    assert lookup(engine, "12345678")[1]["name"] == "Musterbank München"
    with engine.connect() as conn:
        history = conn.execute(select(activations)).mappings().all()
    assert len(history) == 3
    assert history[-1]["previous_id"] == second["version"]
    assert len(list_versions(engine)) == 2


def test_bad_import_does_not_modify_active_version(engine, import_file):
    first = import_file(make_active=True)
    with pytest.raises(ValueError):
        import_file(bank_line() + b"\nBROKEN")
    assert lookup(engine, "12345678")[0]["version"] == first["version"]
    assert len(list_versions(engine)) == 1


def test_future_version_requires_its_validity_date(engine, import_file):
    result = import_file(start=today() + timedelta(days=5))
    with pytest.raises(ValueError, match="noch nicht"):
        activate(engine, result["version"])
    assert lookup(engine, "12345678") == (None, None)


def test_expired_rollback_never_looks_current(engine, import_file):
    result = import_file(start=today() - timedelta(days=10), end=today() - timedelta(days=1))
    with pytest.raises(ValueError, match="abgelaufen"):
        activate(engine, result["version"])
    activate(engine, result["version"], allow_expired=True)
    info, bank = lookup(engine, "12345678")
    assert info["status"] == "expired"
    assert bank is None


def test_validity_boundaries_are_inclusive(engine, import_file):
    result = import_file(start=today(), end=today())
    activate(engine, result["version"])
    assert lookup(engine, "12345678")[0]["status"] == "current"
    assert lookup(engine, "12345678", today() + timedelta(days=1))[0]["status"] == "expired"


def test_conflicting_dates_for_same_file_are_rejected(import_file):
    import_file()
    with pytest.raises(ValueError, match="anderem Gültigkeitszeitraum"):
        import_file(end=today() + timedelta(days=60))


def test_announced_deletion_is_not_actual_deletion(engine, import_file):
    import_file(bank_line(deletion="1", successor="87654321"), make_active=True)
    _, bank = lookup(engine, "12345678")
    assert bank["deletion_announced"] is True
    assert bank["change_flag"] == "U"
    assert bank["successor_bank_code"] == "87654321"
