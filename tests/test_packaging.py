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
    assert "IronAnvil-Experimental.exe" in shown[0]
    assert "No installation or Python" in shown[0]
    assert "Cannot open data directory" in shown[0]


def test_downloads_and_windows_version_properties_match_the_application():
    import ast
    import re
    from ironanvil import __version__, RELEASE_TAG

    root=Path(__file__).resolve().parents[1]
    tree=ast.parse((root/'packaging/version_info.txt').read_text())
    properties={ast.literal_eval(node.args[0]):ast.literal_eval(node.args[1])
                for node in ast.walk(tree) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name) and node.func.id=='StringStruct'}
    assert properties['ProductVersion']==__version__
    assert properties['FileVersion']==__version__+'.0'
    fixed=next(node for node in ast.walk(tree) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Name) and node.func.id=='FixedFileInfo')
    expected=tuple(int(part) for part in __version__.split('.'))+(0,)
    values={keyword.arg:ast.literal_eval(keyword.value) for keyword in fixed.keywords}
    assert values['filevers']==values['prodvers']==expected
    project_version=re.search(r'^version = "([^"]+)"', (root/'pyproject.toml').read_text(),re.M).group(1)
    assert project_version==__version__
    assert RELEASE_TAG.startswith('v'+__version__+'-experimental.')
    assert (root/'docs/releases'/f'{RELEASE_TAG}.md').is_file()
    assert '/releases/tag/'+RELEASE_TAG in (root/'packaging/installer.iss').read_text()


@pytest.mark.parametrize("category", ("plane", "helicopter"))
@pytest.mark.parametrize("side", ("blue", "red", "neutrals"))
def test_compiled_probe_rejects_dcs_route_timing_errors(entrypoint, category, side):
    # The reported support error, then CAP with a lock at the WRONG point.
    points = {1: {"ETA": 0, "ETA_locked": False},
              2: {"ETA": 60, "ETA_locked": False}}
    group = {"name": "REPORTED FLIGHT", "route": {"points": points}}
    saved = {"coalition": {side: {"country": {1: {category: {"group": {1: group}}}}}}}
    with pytest.raises(RuntimeError, match="REPORTED FLIGHT: Route has no waypoints with locked time"):
        entrypoint._check_air_route_timing(saved)
    points[2]["ETA_locked"] = True
    assert entrypoint._check_air_route_timing(saved) == 1
    group["lateActivation"] = True
    with pytest.raises(RuntimeError, match="Late activation requires a locked time at the first waypoint"):
        entrypoint._check_air_route_timing(saved)
    points[1]["ETA_locked"] = True
    points[2]["ETA_locked"] = False
    assert entrypoint._check_air_route_timing(saved) == 1
    del points[1]["ETA"]
    with pytest.raises(RuntimeError, match="Locked waypoint has an invalid ETA"):
        entrypoint._check_air_route_timing(saved)
