from datetime import timedelta

import pytest

from openiban.storage import activate, build_engine, initialize, stage_file, today


def bank_line(
    *,
    code="12345678",
    leader="1",
    name="Musterbank München",
    postal="12345",
    city="München",
    bic="TESTDEFFXXX",
    record_id="000001",
    flag="U",
    deletion="0",
    successor="00000000",
) -> bytes:
    # Synthetic records only; fixed-width layout from the Bundesbank specification.
    fields = [
        code,
        leader,
        name.ljust(58),
        postal,
        city.ljust(35),
        "Musterbank".ljust(27),
        "00000",
        bic.ljust(11),
        "09",
        record_id,
        flag,
        deletion,
        successor,
    ]
    line = "".join(fields).encode("latin-1")
    assert len(line) == 168
    return line


def iban_for(code="12345678", account="0123456789") -> str:
    bban = code + account
    check = 98 - int(bban + "131400") % 97
    return f"DE{check:02d}{bban}"


@pytest.fixture
def engine(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    initialize(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def import_file(engine, tmp_path):
    counter = 0

    def do_import(content=None, *, start=None, end=None, make_active=False):
        nonlocal counter
        counter += 1
        path = tmp_path / f"banks-{counter}.txt"
        path.write_bytes(content if content is not None else bank_line() + b"\r\n")
        result = stage_file(
            engine, path, start or today() - timedelta(days=1), end or today() + timedelta(days=30)
        )
        if make_active:
            activate(engine, result["version"])
        return result

    return do_import
