"""GUI contract checks; run under xvfb-run on a headless Linux machine."""

import os
import sys
import time
import gc

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="Tk needs a display; run xvfb-run -a python -m pytest tests/test_gui.py",
)


@pytest.fixture
def app(tmp_path):
    from ironanvil.gui import Application

    # Tk objects from a previous destroyed test window must be collected on the
    # UI thread, before a later test starts a mission-generation worker.
    gc.collect()
    window = Application()
    window.withdraw()
    window.output_var.set(str(tmp_path))
    try:
        yield window
    finally:
        window.destroy()


def test_global_enemy_switches_apply_to_every_mission(app):
    from ironanvil.gui import MISSION_LABELS

    for mission, label in MISSION_LABELS.items():
        app.mission_var.set(label)
        app._mission_changed()
        for cap, defenses in ((True, True), (False, True), (True, False), (False, False)):
            app.enemy_cap_var.set(cap)
            app.air_defenses_var.set(defenses)
            app._opposition_changed()
            options = app.collect_options()
            assert options.mission == mission
            assert options.enemy_cap is cap
            assert options.air_defenses is defenses
        if mission == "sead":
            assert "no SAM" in app.opposition_help_var.get()
        if mission == "cap":
            assert "unopposed" in app.opposition_help_var.get()


def test_target_coordinates_and_seed_are_validated(app):
    app.latitude_var.set("42.1")
    with pytest.raises(ValueError, match="both latitude and longitude"):
        app.collect_options()
    app.longitude_var.set("42.35")
    app.seed_var.set("reproduce this")
    with pytest.raises(ValueError, match="whole number"):
        app.collect_options()
    app.seed_var.set("12345")
    options = app.collect_options()
    assert (options.target_lat, options.target_lon, options.seed) == (42.1, 42.35, 12345)
    app._clear_target()
    assert app.collect_options().target_lat is None
    app.latitude_var.set("0")
    app.longitude_var.set("0")
    with pytest.raises(ValueError, match="within Caucasus"):
        app.collect_options()


def test_aircraft_limits_mission_choices_and_syria_opponent(app):
    from ironanvil.gui import MISSION_LABELS

    label, aircraft = next((label, aircraft) for label, aircraft in app._aircraft_by_label.items()
                           if aircraft["missions"] and "cap" not in aircraft["missions"])
    app.mission_var.set(MISSION_LABELS["cap"])
    app.aircraft_var.set(label)
    app._aircraft_changed()
    assert MISSION_LABELS["cap"] not in app.mission_combo["values"]
    assert app.collect_options().mission in aircraft["missions"]
    app.theatre_var.set("Syria")
    app._theatre_changed()
    app.opponent_var.set("insurgents")
    assert app.collect_options().opponent == "insurgents"
    app.theatre_var.set("Caucasus")
    app._theatre_changed()
    assert app.opponent_var.get() == "regular"


def test_air_defenses_off_rejects_a_line_with_only_air_defenses(app):
    from ironanvil.gui import MISSION_LABELS

    app.mission_var.set(MISSION_LABELS["line"])
    app.air_defenses_var.set(False)
    for key, variable in app.line_vars.items():
        variable.set(key in {"aaa", "manpads"})
    with pytest.raises(ValueError, match="ground-combat unit"):
        app.collect_options()


def test_first_run_has_two_pilots_and_each_click_chooses_a_fresh_mission(app, monkeypatch):
    from ironanvil import gui

    seeds = iter((123, 456))
    monkeypatch.setattr(gui.secrets, "randbelow", lambda _limit: next(seeds))
    assert app.collect_options().clients == 2
    assert app.collect_options().seed == 456
    assert app.seed_var.get() == ""


def test_generate_button_creates_a_mission_in_the_background(app, monkeypatch):
    from ironanvil import gui
    from zipfile import ZipFile

    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    app.seed_var.set("42")
    responsive = []
    app.after(1, lambda: responsive.append(True))
    app._generate()
    assert app._busy
    assert str(app.generate_button["state"]) == "disabled"
    deadline = time.monotonic() + 30
    while app._busy and time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    assert responsive
    assert not errors
    assert not app._busy
    assert app._last_output.is_file()
    with ZipFile(app._last_output) as archive:
        assert archive.testzip() is None
        assert "mission" in archive.namelist()
    assert "DCS" in app.next_step_var.get()
    assert "Multiplayer" in app.next_step_var.get()


def test_generation_error_explains_how_to_fix_output_permissions(app, monkeypatch, tmp_path):
    from ironanvil import diagnostics, generator, gui

    def cannot_save(_options):
        raise PermissionError("[WinError 5] Access is denied")

    errors = []
    monkeypatch.setattr(generator, "generate", cannot_save)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    monkeypatch.setenv("IRONANVIL_DATA_DIR", str(tmp_path / "Application data"))
    app._generate_worker(app.collect_options(), app._results)
    app._poll_generation()
    assert len(errors) == 1
    assert "Choose another mission folder" in errors[0][1]
    assert str(diagnostics.log_path()) in errors[0][1]
    assert "WinError" not in errors[0][1]
