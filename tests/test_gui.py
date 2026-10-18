"""GUI contract checks; run under xvfb-run on a headless Linux machine."""

import os
import sys

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="Tk needs a display; run xvfb-run -a python -m pytest tests/test_gui.py",
)


@pytest.fixture
def app(tmp_path):
    from ironanvil.gui import Application

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
