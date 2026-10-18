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
    import zipfile
    from dcs import Mission, lua
    from PIL import Image
    import pyproj
    from ironanvil.generator import generate, PLAYER_GROUP
    from ironanvil.mapdata import Chart, ChartStore, TileCache, cache_directory, is_land
    from ironanvil.model import MISSION_LABELS, MissionOptions, aircraft_catalogue, default_output_dir
    from ironanvil.theatres import THEATRES, get_theatre

    checks = []
    catalogue = aircraft_catalogue()
    if not any(item["id"] == "FA_18C_hornet" for item in catalogue):
        raise RuntimeError("The bundled aircraft catalogue is incomplete")
    checks.append(f"Aircraft catalogue: {len(catalogue)} supported aircraft")
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

        missions = []
        for key in THEATRES:
            for mission_type in MISSION_LABELS:
                for opposition in (True, False):
                    options = MissionOptions(map=key, mission=mission_type, clients=2,
                                             enemy_cap=opposition, air_defenses=opposition,
                                             seed=42, tanker=True, awacs=True)
                    path = generate(options, directory / f"{key}-{mission_type}-{opposition}.miz")
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
                        scripts = [name for name in archive.namelist() if name.endswith("ironanvil_runtime.lua")]
                        if len(scripts) != 1 or b"IRON_ANVIL" not in archive.read(scripts[0]):
                            raise RuntimeError(f"Bundled mission runtime is missing: {path.name}")
                        if metadata["options"]["enemy_cap"] is not opposition or metadata["options"]["air_defenses"] is not opposition:
                            raise RuntimeError(f"Enemy toggle mismatch: {path.name}")
                    reloaded = Mission()
                    reloaded.load_file(str(path))
                    if reloaded.terrain.name != get_theatre(key).terrain().name:
                        raise RuntimeError(f"Terrain failed to reload: {path.name}")
                    clients = reloaded.coalition["blue"].find_group(PLAYER_GROUP)
                    if clients is None or len(clients.units) != 2 or any(unit.skill.value != "Client" for unit in clients.units):
                        raise RuntimeError(f"Multiplayer slots failed to reload: {path.name}")
                    missions.append({"map": key, "mission": mission_type, "opposition": opposition})
        checks.append(f"Generated and reloaded {len(missions)} missions: three maps, five types, enemy forces on/off")

    # These destinations are deliberately outside PyInstaller's read-only bundle.
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS).resolve()
        for output in (default_output_dir(), cache_directory(), log_directory()):
            if output.resolve().is_relative_to(bundle):
                raise RuntimeError(f"Application data would be written into its installation: {output}")
    return {"checks": checks, "missions": missions, "mission_count": len(missions),
            "aircraft_count": len(catalogue), "pyproj_version": pyproj.__version__}


def smoke_gui() -> dict:
    """Start the actual Tk application, render every map, and close it in CI."""
    from ironanvil.gui import Application
    from ironanvil.theatres import THEATRES

    app = Application()
    errors = []
    rendered = []

    def callback_error(exception, value, tb):
        errors.append("".join(traceback.format_exception(exception, value, tb)))
        app.quit()

    app.report_callback_exception = callback_error
    try:
        app.update()
        for theatre in THEATRES.values():
            app.theatre_var.set(theatre.label)
            app._theatre_changed()
            app.update()
            rendered.append(theatre.key)
        app.after(1500, app.quit)
        app.mainloop()
        if errors:
            raise RuntimeError("Tk callback failed: " + errors[0])
        if not app.winfo_exists():
            raise RuntimeError("Application closed before the smoke test completed")
        return {"checks": ["Actual desktop window opened", "All three offline maps rendered", "Tk event loop completed"],
                "maps": rendered, "tk_version": app.tk.call("info", "patchlevel")}
    finally:
        app.destroy()


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
