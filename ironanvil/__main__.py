"""Desktop launcher and automation-friendly mission generation commands."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import traceback

from .model import LINE_UNITS, MISSION_LABELS, MissionOptions, aircraft_catalogue
from .theatres import THEATRES
from .weather import WEATHER_LABELS


def parser():
    p = argparse.ArgumentParser(prog="python -m ironanvil", description="Iron Anvil DCS co-op mission generator")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("gui", help="Open the desktop planner (the default)")
    listing = sub.add_parser("list", help="List supported flyable aircraft and mission types")
    listing.add_argument("--json", action="store_true", help="Machine-readable catalogue")
    doctor = sub.add_parser("doctor", help="Check dependencies and generate/reload a mission on each terrain")
    doctor.add_argument("--debug", action="store_true", help="Print tracebacks for failed checks")
    gen = sub.add_parser("generate", help="Generate one ready-to-open .miz mission")
    gen.add_argument("--map", choices=THEATRES, default="caucasus")
    gen.add_argument("--aircraft", default="FA_18C_hornet")
    gen.add_argument("--mission", choices=MISSION_LABELS, default="facility")
    gen.add_argument("--facility-type", choices=("random", "fuel", "command", "ammunition", "factory", "radar"), default="random")
    gen.add_argument("--clients", type=int, default=2)
    gen.add_argument("--difficulty", choices=("easy", "normal", "hard", "extreme"), default="normal")
    gen.add_argument("--enemy-cap", action=argparse.BooleanOptionalAction, default=True,
                     help="Enemy fighter flights, for every mission type")
    gen.add_argument("--air-defenses", action=argparse.BooleanOptionalAction, default=True,
                     help="Enemy SAM, AAA, MANPADS, for every mission type including SEAD")
    gen.add_argument("--target", nargs=2, metavar=("LAT", "LON"), type=float,
                     help="Pin an inland target in decimal latitude/longitude")
    gen.add_argument("--seed", type=int, default=1)
    gen.add_argument("--start", choices=("cold", "hot", "runway", "air"), default="cold")
    gen.add_argument("--time-of-day", choices=("day", "dawn", "dusk", "night", "random"), default="day")
    gen.add_argument("--weather", choices=WEATHER_LABELS, default="clear")
    gen.add_argument("--departure-airport", help="Departure airfield name or numeric ID; all map airfields are available")
    gen.add_argument("--loadout", choices=("auto", "default"), default="auto")
    gen.add_argument("--tanker", action="store_true")
    gen.add_argument("--awacs", action="store_true")
    gen.add_argument("--base-detail", action=argparse.BooleanOptionalAction, default=True)
    gen.add_argument("--opponent", choices=("regular", "insurgents"), default="regular")
    gen.add_argument("--line-units", default="mbt,ifv,infantry,aaa",
                     help="Comma-separated selection: " + ",".join(LINE_UNITS))
    gen.add_argument("--output-dir", type=Path)
    gen.add_argument("--output", type=Path, help="Exact destination .miz file")
    return p


def doctor(debug=False):
    failures = []
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    try:
        import tkinter
        import PIL
        import pyproj
        from dcs import Mission
        from dcs.terrain import Germany
        from .generator import generate
        print(f"PASS dependencies: Tk {tkinter.TkVersion}, Pillow {PIL.__version__}, pyproj {pyproj.__version__}; Cold War Germany available")
    except Exception as exc:
        print(f"FAIL dependencies: {exc}")
        print(f'Install using this interpreter: "{sys.executable}" -m pip install -r requirements.txt')
        if debug:
            traceback.print_exc()
        return 1
    with tempfile.TemporaryDirectory(prefix="ironanvil-doctor-") as folder:
        for key in THEATRES:
            try:
                path = generate(MissionOptions(map=key, enemy_cap=False, air_defenses=False), Path(folder) / f"{key}.miz")
                mission = Mission()
                mission.load_file(str(path))
                from zipfile import ZipFile
                with ZipFile(path) as archive:
                    bad = archive.testzip()
                    if bad:
                        raise RuntimeError(f"Damaged archive member: {bad}")
                    lua = [name for name in archive.namelist() if name.endswith(".lua")]
                    if not lua:
                        raise RuntimeError("Mission runtime script is missing")
                print(f"PASS {key}: generated and reloaded {path.stat().st_size:,}-byte .miz, embedded Lua present")
            except Exception as exc:
                failures.append(key)
                print(f"FAIL {key}: {type(exc).__name__}: {exc}")
                if debug:
                    traceback.print_exc()
    print("DCS in-simulator validation must be performed on a Windows DCS installation.")
    return 1 if failures else 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command in (None, "gui"):
            from .gui import run
            run()
        elif args.command == "list":
            rows = aircraft_catalogue()
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(f"{row['id']:28} {row['name']:26} {', '.join(row['missions'])}")
        elif args.command == "doctor":
            return doctor(args.debug)
        elif args.command == "generate":
            from .generator import generate
            values = vars(args).copy()
            values.pop("command")
            output = values.pop("output")
            target = values.pop("target")
            values["target_lat"], values["target_lon"] = target or (None, None)
            values["line_units"] = tuple(x.strip() for x in values["line_units"].split(",") if x.strip())
            values["output_dir"] = str(values["output_dir"]) if values["output_dir"] else None
            path = generate(MissionOptions(**values).validate(), output)
            print(f"Mission saved: {path}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Iron Anvil: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
