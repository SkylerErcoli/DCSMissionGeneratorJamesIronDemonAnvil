"""Windowed Windows entry point, with diagnostics for the exact frozen program.

This module deliberately imports only the standard library before logs are open.
A missing bundled DLL or application dependency must produce a useful message
instead of disappearing when a user double-clicks the application.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import traceback


class _LogStream:
    """Redirect dependencies' print diagnostics through the rotating app log."""
    encoding = "utf-8"

    def __init__(self, level):
        self.level = level
        self.pending = ""

    def write(self, message):
        self.pending += str(message)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if line.strip():
                logging.log(self.level, "%s", line)
        return len(message)

    def flush(self):
        if self.pending.strip():
            logging.log(self.level, "%s", self.pending)
        self.pending = ""

    def isatty(self):
        return False


def log_directory() -> Path:
    from ironanvil.diagnostics import log_path
    return log_path().parent


def configure_logging() -> Path:
    from ironanvil.diagnostics import configure_logging as configure_app_logging
    path = configure_app_logging()
    if getattr(sys, "frozen", False):
        sys.stdout = _LogStream(logging.INFO)
        sys.stderr = _LogStream(logging.WARNING)
    logging.info("Iron Anvil startup; frozen=%s; executable=%s", getattr(sys, "frozen", False), sys.executable)
    return path


def show_error(message: str) -> None:
    """Keep the Windows error dialog working even when Tcl/Tk could not load."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Iron Anvil", 0x10)
    else:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror("Iron Anvil", message, parent=root)
        finally:
            root.destroy()


def save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def self_test() -> dict:
    """Exercise bundled terrain modules, resources, native libraries, and codecs.

    No network, DCS installation, registry entries, or writes beside the exe are
    needed. Temporary missions are removed on exit. This is not a DCS flight test.
    """
    from io import BytesIO
    from math import hypot
    import zipfile
    from dcs import Mission, lua
    from PIL import Image
    import pyproj
    from ironanvil.airfields import airport_catalogue
    from ironanvil.generator import generate, PLAYER_GROUP
    from ironanvil.mapdata import Chart, ChartStore, TileCache, cache_directory, is_land
    from ironanvil.model import MISSION_LABELS, MissionOptions, aircraft_catalogue, default_output_dir
    from ironanvil.theatres import THEATRES, get_theatre
    from ironanvil.weather import WEATHER_LABELS

    checks = []
    catalogue = aircraft_catalogue()
    if not any(item["id"] == "FA_18C_hornet" for item in catalogue):
        raise RuntimeError("The bundled aircraft catalogue is incomplete")
    checks.append(f"Aircraft catalogue: {len(catalogue)} supported aircraft")
    airport_counts = {key: len(airport_catalogue(key)) for key in THEATRES}
    if airport_counts != {"caucasus": 21, "syria": 224, "germany": 227}:
        raise RuntimeError(f"The bundled airfield catalogues are incomplete: {airport_counts}")
    checks.append("All 472 airfields and heliports in the pinned terrain catalogues")
    # Requires the PROJ database and native pyproj DLLs, not just Python imports.
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x, y = transformer.transform(10, 50)
    if abs(x - 1113194.9079) > 1 or abs(y - 6446275.8410) > 1:
        raise RuntimeError("Bundled geographic projection data failed")
    checks.append("Native PROJ projection and database")

    with tempfile.TemporaryDirectory(prefix="IronAnvil-self-test-") as temporary:
        directory = Path(temporary)
        # Exercise common chart encoders/decoders and the persisted chart cache.
        image = Image.new("RGB", (256, 256), "#54735a")
        store = ChartStore(directory / "charts")
        for kind in ("PNG", "JPEG", "TIFF", "WEBP"):
            buffer = BytesIO()
            image.save(buffer, format=kind)
            buffer.seek(0)
            with Image.open(buffer) as reopened:
                reopened.load()
                if reopened.size != (256, 256):
                    raise RuntimeError(f"{kind} chart codec failed")
        image_path = directory / "chart.png"
        image.save(image_path)
        for key, theatre in THEATRES.items():
            chart = Chart(image_path, theatre.bounds)
            stored = store.save(key, chart)
            loaded = store.load(key)
            if loaded is None or loaded.bounds != chart.bounds or loaded.path != stored.path:
                raise RuntimeError(f"Chart cache did not reload for {key}")
            store.clear(key)
        checks.append("PNG, JPEG, TIFF, WebP and all three chart caches")
        # The offline map cache is usable without internet or preloaded tiles.
        if TileCache(directory / "tiles").get(5, 1, 1, online=False) is not None:
            raise RuntimeError("An empty offline tile cache should return no tile")
        checks.append("Offline map cache")

        cases = []
        for key in THEATRES:
            for mission_type in MISSION_LABELS:
                for opposition in (True, False):
                    cases.append(MissionOptions(map=key, mission=mission_type, clients=2,
                                                enemy_cap=opposition, air_defenses=opposition,
                                                seed=42, tanker=True, awacs=True))
        for key, name in (("caucasus", "Sochi-Adler"), ("syria", "Damascus"), ("germany", "Stendal")):
            cases.append(MissionOptions(map=key, mission="facility", clients=2,
                                        departure_airport=name, seed=42))
        for weather in WEATHER_LABELS:
            cases.append(MissionOptions(map="caucasus", mission="facility", clients=2,
                                        weather=weather, seed=42))
        missions = []
        weather_checks = {}
        facility_checks = []
        support_checks = 0
        for index, options in enumerate(cases):
            path = generate(options, directory / f"mission-{index}.miz")
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError(f"Corrupt generated mission: {path.name}")
                metadata = json.loads(archive.read("ironanvil.json"))
                if not is_land(metadata["target_lat"], metadata["target_lon"]):
                    raise RuntimeError(f"Default target is offshore: {path.name}")
                warehouses = lua.loads(archive.read("warehouses").decode("utf-8"))["warehouses"]
                home = warehouses["airports"][metadata["home_airport_id"]]
                if home["coalition"] != "BLUE" or not home["unlimitedFuel"] or not home["unlimitedMunitions"]:
                    raise RuntimeError(f"Home base cannot supply friendly pilots: {path.name}")
                if options.departure_airport and metadata["home_airport"] != options.departure_airport:
                    raise RuntimeError(f"Selected airfield was not used: {path.name}")
                scripts = [name for name in archive.namelist() if name.endswith("ironanvil_runtime.lua")]
                if len(scripts) != 1 or b"IRON_ANVIL" not in archive.read(scripts[0]):
                    raise RuntimeError(f"Bundled mission runtime is missing: {path.name}")
                for toggle in ("enemy_cap", "air_defenses"):
                    if metadata["options"][toggle] is not getattr(options, toggle):
                        raise RuntimeError(f"Enemy toggle mismatch: {path.name}")
                saved = lua.loads(archive.read("mission").decode("utf-8"))["mission"]
                weather = saved["weather"]
                if options.mission == "facility":
                    sites = metadata["facility_sites"]
                    red_countries = saved["coalition"]["red"]["country"].values()
                    red_statics = {unit["name"]: unit for country in red_countries
                                   for group in country.get("static", {}).get("group", {}).values()
                                   for unit in group["units"].values()}
                    red_vehicles = {group["name"]: group for country in saved["coalition"]["red"]["country"].values()
                                    for group in country.get("vehicle", {}).get("group", {}).values()}
                    if len(sites) < 3 or metadata["facility_decoration_count"] < 24:
                        raise RuntimeError(f"Facility does not contain three detailed sites: {path.name}")
                    if sum(unit["type"] == "Workshop A" for unit in red_statics.values()) > 1:
                        raise RuntimeError(f"Facility repeats its large factory building: {path.name}")
                    for site in sites:
                        if site["decoration_count"] < 8 or site["garrison_units"] < 2 or not site["vehicle_groups"]:
                            raise RuntimeError(f"Facility site lacks decoration or occupants: {path.name}")
                        if any(name not in red_statics for name in site["decoration_statics"] + site["objective_statics"]):
                            raise RuntimeError(f"Facility buildings are missing from the saved mission: {path.name}")
                        occupants = [unit for name in site["vehicle_groups"]
                                     for unit in red_vehicles[name]["units"].values()]
                        if sum(unit["type"] == "Infantry AK" for unit in occupants) < 2:
                            raise RuntimeError(f"Facility occupants are missing from the saved mission: {path.name}")
                    facility_checks.append({"map": options.map, "site_count": len(sites),
                                            "decoration_count": metadata["facility_decoration_count"]})
                blue_planes = {group["name"]: group for country in saved["coalition"]["blue"]["country"].values()
                               for group in country.get("plane", {}).get("group", {}).values()}
                for name, enabled, role in (("TEXACO", options.tanker, "Tanker"), ("OVERLORD", options.awacs, "AWACS")):
                    if not enabled:
                        continue
                    group = blue_planes[name]
                    points = group["route"]["points"]
                    if len(points) != 3 or group["task"] != ("Refueling" if role == "Tanker" else "AWACS"):
                        raise RuntimeError(f"Support aircraft has an incomplete route or role: {path.name}")
                    first_tasks = list(points[1]["task"]["params"]["tasks"].values())
                    if not any(item["id"] == role for item in first_tasks):
                        raise RuntimeError(f"Support aircraft's role does not start immediately: {path.name}")
                    commands = {item["params"]["action"]["id"]: item["params"]["action"]["params"]
                                for item in first_tasks if item["id"] == "WrappedAction"}
                    if (commands.get("SetInvisible", {}).get("value") is not True
                            or commands.get("SetImmortal", {}).get("value") is not True):
                        raise RuntimeError(f"Support aircraft is not protected from hostile AI: {path.name}")
                    orbits = [item for item in points[2]["task"]["params"]["tasks"].values() if item["id"] == "Orbit"]
                    if len(orbits) != 1 or orbits[0]["params"]["pattern"] != "Race-Track":
                        raise RuntimeError(f"Support aircraft lacks its racetrack orbit: {path.name}")
                    if abs(hypot(points[3]["x"] - points[2]["x"], points[3]["y"] - points[2]["y"]) - 25000) > 1:
                        raise RuntimeError(f"Support aircraft lacks its second orbit anchor: {path.name}")
                    support_checks += 1
                if options.weather in ("rain", "storm"):
                    if weather["clouds"]["iprecptns"] != (1 if options.weather == "rain" else 2):
                        raise RuntimeError(f"Precipitation was not serialized: {path.name}")
                    weather_checks[options.weather] = weather["clouds"]["iprecptns"]
                elif options.weather == "fog":
                    if not weather["enable_fog"] or weather["fog"]["visibility"] != 3000:
                        raise RuntimeError(f"Fog was not serialized: {path.name}")
                    weather_checks["fog"] = weather["fog"]
                elif options.weather == "windy":
                    speeds = [weather["wind"][level]["speed"] for level in ("atGround", "at2000", "at8000")]
                    if speeds != [10, 17, 25] or weather["groundTurbulence"] != 15:
                        raise RuntimeError(f"Strong winds were not serialized: {path.name}")
                    weather_checks["windy"] = speeds
            reloaded = Mission()
            reloaded.load_file(str(path))
            if reloaded.terrain.name != get_theatre(options.map).terrain().name:
                raise RuntimeError(f"Terrain failed to reload: {path.name}")
            if reloaded.weather.dict() != weather:
                raise RuntimeError(f"Weather failed to reload: {path.name}")
            clients = reloaded.coalition["blue"].find_group(PLAYER_GROUP)
            if clients is None or len(clients.units) != 2 or any(unit.skill.value != "Client" for unit in clients.units):
                raise RuntimeError(f"Multiplayer slots failed to reload: {path.name}")
            if not reloaded.terrain.airport_by_id(metadata["home_airport_id"]).is_blue():
                raise RuntimeError(f"Selected airfield is not friendly: {path.name}")
            missions.append({"map": options.map, "mission": options.mission,
                             "opposition": options.enemy_cap, "weather": options.weather,
                             "departure": metadata["home_airport"]})
        checks.append(f"Generated and reloaded {len(missions)} missions: all maps/types/opposition, selected airfields and every weather")
        checks.append("Actual serialized rain, thunderstorm, fog and winds verified and reloaded")
        checks.append("Facility strikes contain three occupied decorated sites and at most one large factory")
        checks.append("Support aircraft have immediate roles/protection and complete three-point racetrack routes")

    # These destinations are deliberately outside PyInstaller's read-only bundle.
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS).resolve()
        for output in (default_output_dir(), cache_directory(), log_directory()):
            if output.resolve().is_relative_to(bundle):
                raise RuntimeError(f"Application data would be written into its installation: {output}")
    return {"checks": checks, "missions": missions, "mission_count": len(missions),
            "airport_counts": airport_counts, "weather_checks": weather_checks,
            "facility_checks": facility_checks, "support_checks": support_checks,
            "aircraft_count": len(catalogue), "pyproj_version": pyproj.__version__}


def smoke_gui() -> dict:
    """Render every map/theme and reload real settings without user-data writes."""
    from ironanvil.airfields import airport_catalogue
    from ironanvil.gui import Application, THEME_PALETTES
    from ironanvil.theatres import THEATRES
    from ironanvil.weather import WEATHER_LABELS

    original_data_dir = os.environ.get("IRONANVIL_DATA_DIR")
    with tempfile.TemporaryDirectory(prefix="IronAnvil-gui-test-") as temporary:
        os.environ["IRONANVIL_DATA_DIR"] = temporary
        app = None
        errors = []
        rendered = []

        def callback_error(exception, value, tb):
            errors.append("".join(traceback.format_exception(exception, value, tb)))
            if app is not None:
                app.quit()

        try:
            app = Application()
            app.report_callback_exception = callback_error
            app.update()
            for theme in ("dark", "light"):
                app.theme_var.set(theme)
                app._theme_changed()
                if app.cget("background") != THEME_PALETTES[theme]["bg"]:
                    raise RuntimeError(f"Desktop did not apply the {theme} theme")
                for theatre in THEATRES.values():
                    app.theatre_var.set(theatre.label)
                    app._theatre_changed()
                    app.update()
                    if len(app.departure_combo.cget("values")) != len(airport_catalogue(theatre.key)) + 1:
                        raise RuntimeError(f"Departure selector is incomplete for {theatre.key}")
                    rendered.append({"map": theatre.key, "theme": theme})
            for key, label in WEATHER_LABELS.items():
                if key != "cloudy" and label not in app.weather_combo.cget("values"):
                    raise RuntimeError(f"Weather selector is missing {key}")
            app.departure_var.set("Stendal")
            app.weather_var.set(WEATHER_LABELS["rain"])
            app._save_settings()
            app.after(750, app.quit)
            app.mainloop()
            if errors:
                raise RuntimeError("Tk callback failed: " + errors[0])
            tk_version = app.tk.call("info", "patchlevel")
            app.destroy()
            app = Application()
            app.report_callback_exception = callback_error
            app.update()
            if (app.theme_var.get() != "light" or app.departure_var.get() != "Stendal"
                    or app.weather_var.get() != WEATHER_LABELS["rain"]):
                raise RuntimeError("Preferences did not survive a desktop restart")
            if errors:
                raise RuntimeError("Tk callback failed after restart: " + errors[0])
            return {"checks": ["Actual desktop window opened", "All three offline maps rendered in dark and light modes",
                               "Complete airfield/weather selectors", "Theme, airfield and weather survive restart", "Tk event loop completed"],
                    "maps": rendered, "tk_version": tk_version, "preferences_reloaded": True}
        finally:
            if app is not None:
                app.destroy()
            if original_data_dir is None:
                os.environ.pop("IRONANVIL_DATA_DIR", None)
            else:
                os.environ["IRONANVIL_DATA_DIR"] = original_data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Iron Anvil desktop application")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    modes.add_argument("--smoke-gui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--self-test-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    testing = args.self_test or args.smoke_gui
    report = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)),
              "platform": sys.platform, "timestamp": datetime.now(timezone.utc).isoformat(),
              "mode": "self-test" if args.self_test else "smoke-gui"}
    log_path = None
    try:
        log_path = configure_logging()
        if testing:
            report.update(self_test() if args.self_test else smoke_gui())
            report["ok"] = True
            logging.info("%s passed", report["mode"])
        else:
            import tkinter as tk

            def callback_error(exception, value, tb):
                logging.error("Desktop callback failed", exc_info=(exception, value, tb))
                show_error("Something went wrong. Please try again.\n\n"
                           f"If it keeps happening, share this log with the person who sent you Iron Anvil:\n{log_path}")

            tk.Tk.report_callback_exception = staticmethod(callback_error)
            from ironanvil.gui import run
            run()
        return 0
    except Exception as exc:
        logging.exception("Iron Anvil failed")
        if testing:
            report["error"] = f"{type(exc).__name__}: {exc}"
            report["traceback"] = traceback.format_exc()
        else:
            show_error("Iron Anvil could not open.\n\n"
                       "If you downloaded a ZIP, right-click it, choose Extract All, "
                       "and open IronAnvil.exe from the extracted folder. "
                       "Keep the _internal folder beside the application.\n\n"
                       f"Details to share if the problem continues:\n{log_path or str(exc)}")
        return 1
    finally:
        if testing and args.self_test_output:
            if log_path:
                report["log"] = str(log_path)
            save_report(args.self_test_output, report)


if __name__ == "__main__":
    raise SystemExit(main())
