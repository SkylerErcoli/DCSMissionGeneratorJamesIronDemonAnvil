#!/usr/bin/env python3
"""Build/reload a representative mission matrix without a DCS installation.

The full matrix covers 168 missions: all three maps, five Hornet mission types,
one Apache strike and one Mustang strike, 1/4 clients, and all four starts.
Use --quick for 17 missions. These checks do not substitute for a DCS flight.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dcs import Mission, lua
from ironanvil.generator import generate, PLAYER_GROUP
from ironanvil.model import MissionOptions, MISSION_LABELS
from ironanvil.theatres import THEATRES, get_theatre


def options_matrix(quick=False):
    for map_name in THEATRES:
        for mission in MISSION_LABELS:
            basic = MissionOptions(map=map_name, mission=mission)
            if quick:
                yield basic
            else:
                for clients in (1, 4):
                    for start in ("cold", "hot", "runway", "air"):
                        yield replace(basic, clients=clients, start=start)
    for aircraft in ("AH_64D_BLK_II", "P_51D"):
        for map_name in (("caucasus",) if quick else THEATRES):
            basic = MissionOptions(map=map_name, aircraft=aircraft, mission="line")
            if quick:
                yield basic
            else:
                for clients in (1, 4):
                    for start in ("cold", "hot", "runway", "air"):
                        yield replace(basic, clients=clients, start=start)


def check_mission(path, options, lua_executable=None):
    """Check actual archive data and pydcs reload, not only builder objects."""
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, "Corrupt ZIP member"
        metadata = json.loads(archive.read("ironanvil.json"))
        serialized = lua.loads(archive.read("mission").decode("utf-8"))["mission"]
        warehouses = lua.loads(archive.read("warehouses").decode("utf-8"))["warehouses"]
        assert metadata["options"]["clients"] == options.clients
        assert metadata["options"]["start"] == options.start
        assert metadata["options"]["aircraft"] == options.aircraft
        assert get_theatre(options.map).is_land(metadata["target_lat"], metadata["target_lon"])
        airport = warehouses["airports"][metadata["home_airport_id"]]
        assert airport["coalition"] == "BLUE", "Client home airport is not BLUE"
        assert airport["unlimitedFuel"] and airport["unlimitedMunitions"], "Home supplies are limited"
        assert serialized["theatre"] == get_theatre(options.map).terrain().name
        scripts = [name for name in archive.namelist() if name.endswith("ironanvil_runtime.lua")]
        assert len(scripts) == 1, "Self-contained runtime Lua is missing"
        if lua_executable:
            # loadstring compiles without executing DCS API calls.
            source = archive.read(scripts[0])
            result = subprocess.run([lua_executable, "-e", "assert(loadstring(io.read('*a')))"],
                                    input=source, capture_output=True)
            assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    reloaded = Mission()
    reloaded.load_file(str(path))
    player = reloaded.coalition["blue"].find_group(PLAYER_GROUP)
    assert player is not None, "Reload lost the client flight"
    assert len(player.units) == options.clients, "Incorrect client count after reload"
    assert all(unit.skill.value == "Client" for unit in player.units), "Non-client player slot"
    theatre = get_theatre(options.map)
    for coalition in reloaded.coalition.values():
        for country in coalition.countries.values():
            for group in country.vehicle_group + country.static_group:
                for unit in group.units:
                    point = unit.position.latlng()
                    assert theatre.is_land(point.lat, point.lng), f"Ground object in water: {unit.name}"


def run(directory, quick=False, lua_executable=None):
    cases = list(options_matrix(quick))
    failures = []
    for index, options in enumerate(cases, 1):
        label = f"{options.map}/{options.aircraft}/{options.mission}/{options.clients}/{options.start}"
        try:
            path = generate(options, directory / f"matrix_{index:03d}.miz")
            check_mission(path, options, lua_executable)
        except Exception as exc:
            failures.append((label, f"{type(exc).__name__}: {exc}"))
            print(f"FAIL {label}: {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"PASS {index}/{len(cases)} {label}", flush=True)
    print(f"Matrix: {len(cases) - len(failures)} passed, {len(failures)} failed; "
          f"Lua syntax {'checked' if lua_executable else 'not checked (no Lua executable selected)'}. ")
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Build 17 representative missions")
    parser.add_argument("--output-dir", type=Path, help="Keep generated missions in this directory")
    parser.add_argument("--lua", help="Optional Lua executable for embedded script syntax checks")
    args = parser.parse_args()
    lua_executable = args.lua or shutil.which("lua5.1")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        return run(args.output_dir, args.quick, lua_executable)
    with tempfile.TemporaryDirectory(prefix="ironanvil-matrix-") as directory:
        return run(Path(directory), args.quick, lua_executable)


if __name__ == "__main__":
    raise SystemExit(main())
