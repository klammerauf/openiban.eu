from datetime import UTC, date, datetime, timedelta

import pytest

from openiban import updater as u
from openiban.storage import activate, stage_file
from tests.conftest import bank_line

START = date(2026, 9, 7)
END = date(2026, 12, 6)
NEXT = date(2026, 12, 7)
UNTIL = date(2027, 3, 7)
NOW = datetime(2026, 12, 6, 4, tzinfo=UTC)
URL = "https://www.bundesbank.de/resource/blob/123/next.txt"


def page(start=NEXT, end=UNTIL):
    return (
        f'<a href="{URL}">Bankleitzahlendateien <small>gültig vom '
        f"{start:%d.%m.%Y} bis {end:%d.%m.%Y}</small></a>"
    ).encode()


@pytest.fixture
def setup(engine, tmp_path):
    def content(changed=0):
        return b"\r\n".join(
            bank_line(
                code=f"{10000000 + i}",
                record_id=f"{i + 1:06}",
                name="Neu" if i < changed else "Alt",
            )
            for i in range(1000)
        )

    original = tmp_path / "old.txt"
    original.write_bytes(content())
    version = stage_file(engine, original, START, END)["version"]
    activate(engine, version, on_date=START)
    directory = tmp_path / "updates"

    def fetch(url, limit):
        return page() if url == u.SOURCE_URL else content(1)

    return directory, fetch, version, content


def test_future_then_activation_and_idempotency(engine, setup):
    directory, fetch, old, _ = setup
    state = u.auto_check(engine, directory, now=NOW, fetch=fetch)
    assert state["candidates"][0]["status"] == "approved"
    assert u.auto_activate(engine, directory, now=NOW)["result"] == "no_change"
    due = NOW + timedelta(days=1)
    assert u.auto_activate(engine, directory, now=due)["result"] == "activated"
    assert u.auto_activate(engine, directory, now=due)["result"] == "no_change"
    assert u.snapshot(engine)[0]["id"] != old
    # A deliberate rollback must not be silently undone by automation.
    activate(engine, old, allow_expired=True, on_date=NEXT)
    u.auto_check(engine, directory, now=due, fetch=fetch)
    assert u.auto_activate(engine, directory, now=due)["result"] == "no_change"
    assert u.snapshot(engine)[0]["id"] == old


def test_download_failure_preserves_active_and_blocks_activation(engine, setup):
    directory, fetch, old, _ = setup
    u.auto_check(engine, directory, now=NOW, fetch=fetch)

    def fail(url, limit):
        raise OSError("offline")

    with pytest.raises(OSError):
        u.auto_check(engine, directory, now=NOW, fetch=fail)
    with pytest.raises(ValueError, match="blocked"):
        u.auto_activate(engine, directory, now=NOW + timedelta(days=1))
    assert u.snapshot(engine)[0]["id"] == old


def test_large_change_requires_review(engine, setup):
    directory, _, old, content = setup
    state = u.auto_check(
        engine,
        directory,
        now=NOW,
        fetch=lambda url, limit: page() if url == u.SOURCE_URL else content(101),
    )
    assert state["candidates"][0]["status"] == "needs_review"
    assert state["warnings"]
    assert u.auto_activate(engine, directory, now=NOW + timedelta(days=1))["result"] == "no_change"
    assert u.snapshot(engine)[0]["id"] == old


def test_stale_check_cannot_activate(engine, setup):
    directory, fetch, _, _ = setup
    u.auto_check(engine, directory, now=NOW, fetch=fetch)
    with pytest.raises(ValueError, match="blocked"):
        u.auto_activate(engine, directory, now=NOW + timedelta(days=3))


def test_compare_and_swap(engine, setup):
    _, _, version, _ = setup
    with pytest.raises(ValueError, match="has changed"):
        activate(engine, version, on_date=START, expected_previous_id="wrong")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.bundesbank.de/a.txt",
        "https://evil.test/a.txt",
        "https://www.bundesbank.de@evil.test/a.txt",
    ],
)
def test_external_download_rejected(url):
    with pytest.raises(ValueError):
        u.allowed_url(url)


def test_discovery_rejects_ambiguous_and_invalid_dates():
    with pytest.raises(ValueError):
        u.discover(page().decode().replace("07.12.2026", "08.12.2026"), NOW.date())
    with pytest.raises(ValueError):
        u.discover(page().decode() + page().decode().replace("next.txt", "other.txt"), NOW.date())
    assert u.discover(page().decode(), NOW.date())[0].valid_from == NEXT
