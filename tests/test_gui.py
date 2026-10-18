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
def app(tmp_path, monkeypatch):
    from ironanvil.gui import Application

    # Tk objects from a previous destroyed test window must be collected on the
    # UI thread, before a later test starts a mission-generation worker.
    gc.collect()
    monkeypatch.setenv("IRONANVIL_DATA_DIR", str(tmp_path / "Application data"))
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


def test_dark_theme_covers_inputs_popups_and_scroll_panels_and_can_switch(app):
    from tkinter import ttk
    from ironanvil.gui import THEME_PALETTES

    assert app.theme_var.get() == "dark"
    for theme in ("dark", "light", "dark"):
        app.theme_var.set(theme)
        app._theme_changed()
        palette = THEME_PALETTES[theme]
        style = ttk.Style(app)
        assert app.cget("background") == palette["bg"]
        assert style.lookup("TCombobox", "fieldbackground", ("readonly",)) == palette["field"]
        assert style.lookup("TCombobox", "foreground", ("readonly",)) == palette["foreground"]
        assert style.lookup("TCombobox", "foreground", ("disabled",)) == palette["muted"]
        assert all(canvas.cget("background") == palette["surface"] for canvas in app._settings_canvases)
        popup = app.tk.call("ttk::combobox::PopdownWindow", app.departure_combo)
        assert app.tk.call(f"{popup}.f.l", "cget", "-background") == palette["field"]
        assert app.tk.call(f"{popup}.f.l", "cget", "-foreground") == palette["foreground"]


@pytest.mark.parametrize("map_key,count", [("caucasus", 21), ("syria", 224), ("germany", 227)])
def test_departure_list_contains_every_airfield_and_type_search_does_not_hide_choices(app, map_key, count):
    from ironanvil.airfields import airport_catalogue
    from ironanvil.gui import AUTOMATIC_AIRFIELD
    from ironanvil.theatres import THEATRES

    app.theatre_var.set(THEATRES[map_key].label)
    app._theatre_changed()
    all_names = {airport["name"] for airport in airport_catalogue(map_key)}
    assert len(all_names) == count
    assert set(app.departure_combo["values"]) == {AUTOMATIC_AIRFIELD, *all_names}
    name = sorted(all_names)[-1]
    app.departure_var.set(name[:3])
    app._filter_departures()
    assert name in app.departure_combo["values"]
    app.departure_var.set("")
    app._filter_departures()
    assert set(app.departure_combo["values"]) == {AUTOMATIC_AIRFIELD, *all_names}


def test_airfield_selection_is_validated_and_resets_on_map_change(app):
    app.departure_var.set("batumi")
    assert app.collect_options().departure_airport == "Batumi"
    app.departure_var.set("not an airfield")
    with pytest.raises(ValueError, match="Choose a departure airfield"):
        app.collect_options()
    app.departure_var.set("Batumi")
    app.theatre_var.set("Syria")
    app._theatre_changed()
    assert app.collect_options().departure_airport is None


def test_all_weather_presets_and_facility_choices_are_available(app):
    from ironanvil.gui import FACILITY_LABELS, MISSION_LABELS
    from ironanvil.weather import WEATHER_LABELS

    assert len(app.weather_combo["values"]) == 9
    for key, label in WEATHER_LABELS.items():
        app.weather_var.set(label)
        assert app.collect_options().weather == key
    for key, label in FACILITY_LABELS.items():
        app.facility_var.set(label)
        assert app.collect_options().facility_type == key
    app.mission_var.set(MISSION_LABELS["convoy"])
    app._mission_changed()
    assert str(app.facility_combo["state"]) == "disabled"
    app.mission_var.set(MISSION_LABELS["facility"])
    app._mission_changed()
    assert str(app.facility_combo["state"]) == "readonly"


def test_preferences_survive_reopening_and_preserve_other_feature_settings(app, tmp_path):
    from ironanvil.gui import Application, FACILITY_LABELS
    from ironanvil.preferences import load_preferences, save_preferences
    from ironanvil.weather import WEATHER_LABELS

    save_preferences({"update_channel": "stable", "mission": {"future_setting": "keep"}})
    app.theme_var.set("light")
    app.departure_var.set("Batumi")
    app.weather_var.set(WEATHER_LABELS["fog"])
    app.facility_var.set(FACILITY_LABELS["fuel"])
    app.output_var.set(str(tmp_path / "My missions"))
    app.clients_var.set("4")
    app.destroy()
    reopened = Application()
    reopened.withdraw()
    try:
        assert reopened.theme_var.get() == "light"
        assert reopened.departure_var.get() == "Batumi"
        assert reopened.weather_var.get() == WEATHER_LABELS["fog"]
        assert reopened.facility_var.get() == FACILITY_LABELS["fuel"]
        assert reopened.output_var.get() == str(tmp_path / "My missions")
        assert reopened.collect_options().clients == 4
        assert load_preferences()["update_channel"] == "stable"
        assert load_preferences()["mission"]["future_setting"] == "keep"
    finally:
        reopened.destroy()


def test_check_for_updates_runs_without_blocking_window(app, monkeypatch):
    from ironanvil import gui, updater

    messages = []
    monkeypatch.setattr(updater, "check_for_update", lambda: None)
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args, **kwargs: messages.append(args))
    responsive = []
    app.after(1, lambda: responsive.append(True))
    app._check_updates()
    assert app._updating
    deadline = time.monotonic() + 5
    while app._updating and time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    assert responsive
    assert not app._updating
    assert "up to date" in messages[0][0]
    assert str(app.generate_button["state"]) == "normal"


def test_update_download_is_verified_by_updater_before_launch_and_window_closes(app, monkeypatch, tmp_path):
    from ironanvil import gui, updater
    from ironanvil.preferences import load_preferences

    installer = tmp_path / "IronAnvil-Setup-x64.exe"
    info = updater.UpdateInfo(version="99.0.0", installer_url="https://example.invalid/setup.exe",
                              sha256="a" * 64, release_url="https://example.invalid/release")
    calls = []
    monkeypatch.setattr(gui.sys, "platform", "win32")
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(updater, "download_update", lambda update, progress_callback: installer)
    monkeypatch.setattr(updater, "launch_update", lambda path, expected_sha256: calls.append((path, expected_sha256)))
    app.theme_var.set("light")
    app._updating = True
    app._update_results.put(("checked", info))
    app._poll_updates()
    deadline = time.monotonic() + 5
    while not app._closed and time.monotonic() < deadline:
        app._poll_updates()
        time.sleep(0.01)
    assert calls == [(installer, info.sha256)]
    assert app._closed
    assert load_preferences()["theme"] == "light"


def test_failed_update_keeps_current_app_usable(app, monkeypatch):
    from ironanvil import gui

    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    app._updating = True
    app.generate_button.configure(state="disabled")
    app._update_results.put(("update-error", "The update could not be verified."))
    app._poll_updates()
    assert not app._closed
    assert not app._updating
    assert str(app.generate_button["state"]) == "normal"
    assert "keep using your current version" in errors[0][1]


def test_experimental_operation_controls_preserve_same_aircraft_coop(app):
    from ironanvil.operations import OPERATION_LABELS,PACE_LABELS
    from ironanvil.gui import MISSION_LABELS
    aircraft=app.aircraft_var.get()
    for operation in ('broken_relay','supply_denial'):
        app.operation_var.set(OPERATION_LABELS[operation]);app._operation_changed()
        app.pace_var.set(PACE_LABELS['compact']);app.response_var.set(False)
        options=app.collect_options()
        assert options.operation==operation and options.mission=='facility'
        assert options.pace=='compact' and not options.enemy_response
        assert app.aircraft_var.get()==aircraft
        assert str(app.facility_combo['state'])=='disabled'
    app.mission_var.set(MISSION_LABELS['convoy']);app._mission_changed()
    assert app.collect_options().operation=='classic'


def test_loading_recipe_retains_this_computers_output_and_pinned_target(app,tmp_path):
    from ironanvil.model import MissionOptions
    from ironanvil.recipes import write_recipe
    output=app.output_var.get()
    recipe=write_recipe(MissionOptions(map='syria',operation='supply_denial',seed=75,
        weather='rain',clients=4,enemy_response=False,output_dir='Z:/My Friends Missions'),tmp_path/'friend.json')
    app._load_recipe(recipe)
    options=app.collect_options()
    assert options.map=='syria' and options.operation=='supply_denial' and options.seed==75
    assert options.output_dir==output and options.weather=='rain' and options.clients==4
    assert not options.enemy_response


def test_named_preset_reloads_operation_and_protects_other_preferences(app,monkeypatch):
    from ironanvil import gui
    from ironanvil.operations import OPERATION_LABELS
    from ironanvil.preferences import load_preferences,save_preferences
    save_preferences({'unknown_future_setting':'keep'})
    monkeypatch.setattr(gui.simpledialog,'askstring',lambda *a,**k:'Friday squadron')
    app.operation_var.set(OPERATION_LABELS['supply_denial']);app._operation_changed()
    app.seed_var.set('123');app._save_preset()
    app.seed_var.set('999');app._load_preset()
    assert app.collect_options().seed==123 and app.collect_options().operation=='supply_denial'
    assert load_preferences()['unknown_future_setting']=='keep'
    assert 'Friday squadron' in app.preset_combo['values']


def test_open_briefing_uses_generated_local_document(app,tmp_path,monkeypatch):
    import zipfile
    from ironanvil import gui
    path=tmp_path/'My mission.miz'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('ironanvil-briefing.html','<html>My local briefing</html>')
    app._last_output=path
    opened=[];monkeypatch.setattr(gui.webbrowser,'open',opened.append)
    app._open_briefing()
    assert len(opened)==1 and opened[0].startswith('file:') and opened[0].endswith('My%20mission.html')
