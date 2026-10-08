import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "notify", Path(__file__).parents[1] / "deployment/notifications/notify.py"
)
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


def test_warning_dedup_reminder_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "STATE", tmp_path / "state.json")
    clock = [100000]
    monkeypatch.setattr(notify.time, "time", lambda: clock[0])
    issues = ["Fehler"]
    monkeypatch.setattr(notify, "problems", lambda: issues.copy())
    sent = []
    monkeypatch.setattr(notify, "send", lambda *args: sent.append(args))
    notify.check({})
    notify.check({})
    assert len(sent) == 1
    clock[0] += 86401
    notify.check({})
    assert len(sent) == 2
    issues.clear()
    notify.check({})
    notify.check({})
    assert len(sent) == 3
    assert sent[-1][1] == "Entwarnung"


def test_failed_send_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(notify, "problems", lambda: ["Fehler"])

    def fail(*args):
        raise OSError("offline")

    monkeypatch.setattr(notify, "send", fail)
    with pytest.raises(OSError):
        notify.check({})
    assert not notify.STATE.exists()
    sent = []
    monkeypatch.setattr(notify, "send", lambda *args: sent.append(args))
    notify.check({})
    assert len(sent) == 1
    assert notify.STATE.stat().st_mode & 0o777 == 0o600
