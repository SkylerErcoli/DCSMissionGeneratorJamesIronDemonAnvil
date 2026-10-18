"""Diagnostics must survive frozen startup failures without opening CI dialogs."""
import importlib.util
import json
import logging
from pathlib import Path

import pytest


@pytest.fixture
def entrypoint():
    path = Path(__file__).resolve().parents[1] / "packaging" / "entrypoint.py"
    spec = importlib.util.spec_from_file_location("ironanvil_windows_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_mode_records_import_failure_without_a_dialog(entrypoint, tmp_path, monkeypatch):
    report = tmp_path / "reports" / "startup.json"
    log = tmp_path / "startup.log"
    monkeypatch.setattr(entrypoint, "configure_logging", lambda: log)

    def missing_dependency():
        raise ImportError("A required native library could not load")

    monkeypatch.setattr(entrypoint, "self_test", missing_dependency)
    monkeypatch.setattr(entrypoint, "show_error", lambda *args: pytest.fail("CI must not open dialogs"))
    assert entrypoint.main(["--self-test", "--self-test-output", str(report)]) == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "ImportError" in payload["error"]
    assert "native library" in payload["traceback"]
    assert payload["log"] == str(log)


def test_test_mode_records_success_and_frozen_status(entrypoint, tmp_path, monkeypatch):
    report = tmp_path / "startup.json"
    monkeypatch.setattr(entrypoint, "configure_logging", lambda: tmp_path / "startup.log")
    monkeypatch.setattr(entrypoint.sys, "frozen", True, raising=False)
    monkeypatch.setattr(entrypoint, "self_test", lambda: {"mission_count": 30, "checks": ["runtime bundled"]})
    assert entrypoint.main(["--self-test", "--self-test-output", str(report)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["frozen"] is True
    assert payload["mission_count"] == 30
    assert payload["checks"] == ["runtime bundled"]


def test_print_diagnostics_are_complete_lines(entrypoint, caplog):
    stream = entrypoint._LogStream(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        stream.write("Cannot load ")
        assert "Cannot load" not in caplog.text
        stream.write("terrain\nAnother warning")
        stream.flush()
    assert "Cannot load terrain" in caplog.text
    assert "Another warning" in caplog.text


def test_nontechnical_startup_error_shows_recovery_and_log(entrypoint, tmp_path, monkeypatch):
    log = tmp_path / "startup.log"
    shown = []

    def failure():
        raise OSError("Cannot open data directory")

    monkeypatch.setattr(entrypoint, "configure_logging", failure)
    monkeypatch.setattr(entrypoint, "show_error", shown.append)
    assert entrypoint.main([]) == 1
    assert len(shown) == 1
    assert "Extract All" in shown[0]
    assert "_internal" in shown[0]
    assert "Cannot open data directory" in shown[0]
