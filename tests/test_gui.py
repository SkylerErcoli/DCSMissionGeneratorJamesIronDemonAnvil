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


def test_recovery_and_withdrawal_choices_survive_recipe_and_restart(app,tmp_path):
    from ironanvil.gui import Application
    from ironanvil.model import MissionOptions,RECOVERY_LABELS
    from ironanvil.recipes import write_recipe
    recipe=write_recipe(MissionOptions(operation='rolling_thunder',recovery='home_or_alternate',
        allow_withdrawal=False,seed=91),tmp_path/'recovery.json')
    app._load_recipe(recipe)
    assert app.recovery_var.get()==RECOVERY_LABELS['home_or_alternate']
    options=app.collect_options()
    assert options.operation=='rolling_thunder' and options.recovery=='home_or_alternate' and not options.allow_withdrawal
    app._save_settings();app.destroy()
    reopened=Application();reopened.withdraw()
    try:
        options=reopened.collect_options()
        assert options.recovery=='home_or_alternate' and not options.allow_withdrawal
    finally:reopened.destroy()


def test_preview_is_async_writes_no_mission_and_matches_generated_plan(app,tmp_path):
    import json,zipfile
    from ironanvil.operations import OPERATION_LABELS
    app.deiconify();app.geometry('1240x820');app.update()
    app.operation_var.set(OPERATION_LABELS['rolling_thunder']);app._operation_changed()
    app.seed_var.set('');app._preview()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    assert not app._busy and app._preview_metadata is not None
    assert app.seed_var.get() and not list(tmp_path.glob('*.miz'))
    expected=app._preview_metadata['planner']
    assert app.map_view.canvas.find_withtag('mission-plan')
    for point in expected['points']:
        x,y=app.map_view.viewport.to_pixel(point['lat'],point['lon'])
        assert 0<=x<=app.map_view.viewport.width and 0<=y<=app.map_view.viewport.height
    app._generate()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    assert not app._busy and app._last_output
    with zipfile.ZipFile(app._last_output) as archive:actual=json.loads(archive.read('ironanvil.json'))
    assert actual['planner']==expected
    assert app.seed_var.get()=='' # A preview does not lock all later Generate clicks.
    first_seed=actual['options']['seed']
    app._generate()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    with zipfile.ZipFile(app._last_output) as archive:second=json.loads(archive.read('ironanvil.json'))
    assert second['options']['seed']!=first_seed and second['planner']!=expected


def test_automatic_preview_seed_is_not_saved_as_a_permanent_replay(app):
    from ironanvil.preferences import load_preferences
    app._preview()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    app._save_settings()
    assert app.seed_var.get() and load_preferences()['mission']['seed']==''
    app.seed_var.set('731');app._save_settings()
    assert load_preferences()['mission']['seed']=='731' and 'Fixed variation: 731' in app.quick_help_var.get()


def test_search_preview_hides_exact_sites_and_changed_settings_clear_it(app):
    from ironanvil.model import INTELLIGENCE_LABELS
    app.deiconify();app.update()
    app.intelligence_var.set(INTELLIGENCE_LABELS['search']);app._preview()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    assert app._preview_metadata
    assert {point['role'] for point in app._preview_metadata['planner']['points']}=={'home','alternate','search'}
    app.clients_var.set('3');app.update()
    assert app._preview_metadata is None and not app.map_view.canvas.find_withtag('mission-plan')


def test_stale_preview_is_not_displayed_after_settings_change(app):
    from ironanvil.generator import build_mission
    app.seed_var.set('4')
    app._request_signature=app._input_signature()
    _,metadata=build_mission(app.collect_options())
    app.seed_var.set('5')
    app._results.put((True,{'kind':'preview','metadata':metadata}));app._poll_generation()
    assert app._preview_metadata is None and 'Settings changed' in app.status_var.get()


def test_nearby_plan_labels_remain_readable_and_inside_map(app):
    app.deiconify();app.geometry('1240x820');app.update()
    roles=('home','required','bonus','response','delivery','alternate')
    app.map_view.set_plan({'points':[{'role':role,'label':'Nearby '+role,'lat':42.1+index*.001,'lon':43.1}
                                    for index,role in enumerate(roles)]},fit=True)
    app.update();app.map_view._render()
    canvas=app.map_view.canvas
    boxes=[canvas.bbox(item) for item in canvas.find_withtag('mission-plan-label')]
    assert len(boxes)==len(roles)
    for index,box in enumerate(boxes):
        assert 0<=box[0]<box[2]<=canvas.winfo_width()
        assert 0<=box[1]<box[3]<=canvas.winfo_height()
        assert not any(box[0]<other[2] and box[2]>other[0] and box[1]<other[3] and box[3]>other[1]
                       for other in boxes[:index])


def test_quick_first_run_has_workable_defaults_and_keeps_details_optional(app):
    options=app.collect_options()
    assert app.setup_notebook.tab(app.setup_notebook.select(),'text')=='Quick setup'
    assert options.start=='cold' and options.weather=='clear' and options.time_of_day=='day'
    assert options.pace=='compact' and options.recovery=='home_or_alternate'
    assert options.loadout=='auto' and options.clients==2
    assert not options.enemy_cap and options.air_defenses and options.enemy_response
    assert app.pressure_var.get()=='Balanced'
    assert app.classic_type_frame.winfo_manager()=='' and app.line_frame.winfo_manager()==''


def test_quick_picker_covers_supported_missions_without_changing_aircraft(app):
    from ironanvil.quickstart import SCENARIOS
    aircraft=app.aircraft_var.get()
    for label,mission,operation,_ in SCENARIOS.values():
        app.scenario_var.set(label);app._scenario_changed()
        options=app.collect_options()
        assert (options.mission,options.operation)==(mission,operation)
        assert app.aircraft_var.get()==aircraft
        if mission=='cap':assert options.enemy_cap
        if operation=='classic':assert 'ground response' not in app.pressure_help_var.get()


def test_quick_presets_are_shortcuts_and_manual_changes_survive_restart(app):
    from ironanvil.gui import Application
    app.pressure_var.set('Challenging');app._pressure_changed()
    assert app.collect_options().enemy_cap and app.collect_options().difficulty=='hard'
    app.air_defenses_var.set(False)
    assert app.pressure_var.get()=='Custom'
    app.start_var.set('hot');app.seed_var.set('921');app._save_settings();app.destroy()
    reopened=Application();reopened.withdraw()
    try:
        options=reopened.collect_options()
        assert options.start=='hot' and options.seed==921 and options.difficulty=='hard'
        assert options.enemy_cap and not options.air_defenses and reopened.pressure_var.get()=='Custom'
    finally:reopened.destroy()


def test_recommended_setup_preserves_player_choices_and_pinned_target(app):
    app.clients_var.set('4');app._map_selected(42.1,42.35);app.seed_var.set('73')
    aircraft=app.aircraft_var.get();output=app.output_var.get()
    app.start_var.set('hot');app.pressure_var.set('Challenging');app._pressure_changed()
    app._recommended_setup();options=app.collect_options()
    assert (options.target_lat,options.target_lon)==(42.1,42.35)
    assert str(app.quick_distance_combo['state'])=='disabled' and 'map pin' in app.quick_help_var.get()
    assert options.clients==4 and options.seed==73 and app.aircraft_var.get()==aircraft and options.output_dir==output
    assert options.start=='cold' and options.pace=='compact' and not options.enemy_cap
    app._clear_target();assert str(app.quick_distance_combo['state'])=='readonly'


def test_quick_fighter_only_aircraft_gets_a_supported_patrol(app):
    from ironanvil.quickstart import SCENARIOS
    label=next(label for label,item in app._aircraft_by_label.items() if item['missions']==['cap'])
    app.aircraft_var.set(label);app._aircraft_changed()
    assert list(app.scenario_combo['values'])==[SCENARIOS['cap'][0]]
    assert app.collect_options().mission=='cap' and app.collect_options().enemy_cap
    app.pressure_var.set('Relaxed');app._pressure_changed()
    assert not app.collect_options().enemy_cap and 'unopposed' in app.opposition_help_var.get()


def test_quick_essential_controls_and_generate_fit_a_small_window(app):
    app.deiconify();app.geometry('1024x700');app.update()
    canvas=app._settings_canvases[0]
    for combo in (app.scenario_combo,app.pressure_combo):
        assert combo.winfo_rootx()+combo.winfo_width()<=canvas.winfo_rootx()+canvas.winfo_width()
        assert combo.winfo_rooty()+combo.winfo_height()<=canvas.winfo_rooty()+canvas.winfo_height()
    assert app.generate_button.winfo_rooty()+app.generate_button.winfo_height()<=app.winfo_rooty()+app.winfo_height()
    assert app.coordinate_frame.winfo_manager()==''
    app._toggle_coordinates();assert app.coordinate_frame.winfo_manager()=='grid'
    app._toggle_coordinates();assert app.coordinate_frame.winfo_manager()==''


def test_new_variation_changes_only_seed_and_previews_without_saving(app,tmp_path,monkeypatch):
    from ironanvil import gui
    from dataclasses import replace
    app.seed_var.set('42');before=app.collect_options()
    monkeypatch.setattr(gui.secrets,'randbelow',lambda _:314159)
    app._new_variation()
    deadline=time.monotonic()+20
    while app._busy and time.monotonic()<deadline:app.update();time.sleep(.01)
    assert app._preview_metadata and app.collect_options()==replace(before,seed=314159)
    assert not list(tmp_path.glob('*.miz'))
