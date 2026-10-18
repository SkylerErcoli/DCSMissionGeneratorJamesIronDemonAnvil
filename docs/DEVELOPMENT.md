# Development and source installation

The packaged Windows app is the recommended route for players. See [the main README](../README.md) for its download and launch instructions. This guide covers running from source, optional command-line use, and development.

## Source installation on Windows

Install **Python 3.10 or newer**, including Tcl/Tk. Open a terminal in the repository folder and run:

```bat
py -3 -m pip install -r requirements.txt
```

Double-click **`run_gui.pyw`**, or run:

```bat
py -3 -m ironanvil
```

The pinned GitHub pydcs revision includes Cold War Germany; the PyPI release with the same version number does not. If an older pydcs installation takes precedence, run **`fix_pydcs.bat`**, then **`doctor.bat`**. Use the same Python for installation and launch. `run_gui.bat` retains console errors; the `.pyw` launcher displays errors and writes `gui_error.log`.

Generated missions default to `Saved Games\DCS\Missions\IronAnvilExperimental` on this branch, or an existing `DCS.openbeta` folder. The GUI output directory is configurable.

## Optional command-line interface

```bat
py -3 -m ironanvil list
py -3 -m ironanvil doctor
py -3 -m ironanvil generate --map syria --aircraft FA_18C_hornet --mission line --clients 2 --line-units mbt,ifv,infantry --no-enemy-cap --no-air-defenses --seed 42
py -3 -m ironanvil generate --map germany --mission facility --target 52.55 11.4 --start hot --output my-mission.miz
py -3 -m ironanvil generate --map syria --mission facility --facility-type fuel --weather rain --departure-airport Incirlik
```

`generate --help` lists all options; `list --json` prints a machine-readable catalogue. Linux output defaults to `~/IronAnvilExperimental/Missions`; `--output-dir` overrides it.

## Development and cloud environment

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ironanvil doctor
python -m pytest -q
python tools/test_matrix.py
python tools/test_lua.py
```

Tk needs a display. On headless Linux, use `xvfb-run -a python -m pytest -q`. Lua runtime tests require **Lua 5.1**. Optional checks report skips when their tools are absent.

[`tools/setup_cloud.sh`](../tools/setup_cloud.sh) prepares the cloud checkout with a virtual environment outside the source tree and verified Debian packages for Xvfb/Lua, without root access. Use the existing checkout: each cloud task is already isolated. Do not create a Git worktree unless the user explicitly requests one. [Validation details](VALIDATION.md) record completed checks and remaining limits.

## Building the portable Windows app

Use **64-bit CPython 3.12 on Windows**, including Tcl/Tk. Run `tools/build_experimental_windows.ps1` from PowerShell. It installs the pinned build requirements unless `-SkipInstall` is passed. Inno Setup is not used by the experimental build.

The output is **`dist/IronAnvil-Experimental.exe`** and `dist/SHA256SUMS.txt`. PyInstaller bundles Python, Tcl/Tk, pydcs, PROJ, Pillow and offline geography into one executable. It extracts runtime libraries to the normal Windows temporary area; preferences/cache/missions stay outside that extraction and outside the EXE folder. It does not create an installer or ZIP.

The native probe clears Python from PATH, runs 25 representative generated/reloaded missions and a real GUI smoke/restart check, and verifies offline relief, ownership/navigation, paths with spaces and a deny-write application-folder ACL. It then replaces the EXE and runs a separate desktop state probe using existing external preferences. An existing mission must stay byte-for-byte unchanged. Reports are written to `test-results/portable-*.json`.

This verifies portable file replacement and settings compatibility, not installation or migration from every historical executable. Previous experimental installer users can run the downloaded EXE directly with the same external preferences. Their old Start shortcut remains pointed at the installed copy. No old installer downloads, registry writes or stable installation tests are in the normal release path. Historical assets and stable 1.2 remain untouched.

The [workflow](../.github/workflows/experimental-release.yml) runs source/Lua regression checks on source checkpoints; its Linux runner is only a development test host, not a Linux application product. Windows packaging/publication occurs only for `[publish-preview]` or workflow dispatch. Windows-specific source checks and native portable probes complement the full source/Lua suite. The broad mission matrix and geographic diversity report are run deliberately during feature development rather than redundantly on every release. Existing immutable tags/assets are never replaced; new binaries require a new version/tag and are prereleases with `--latest=false`.

For developer-only geography rebuilds, see [GEOGRAPHY.md](experimental/GEOGRAPHY.md). Runtime users do not need Shapely, NumPy or source downloads.

## Mission implementation notes

- Enemy CAP and enemy air defenses are independent for every mission type. Disabling air defenses removes enemy SAMs, AAA, MANPADS, and convoy anti-aircraft escorts, including categories selected in the fortified-line panel. SEAD then targets command/support vehicles; CAP with enemy fighters disabled becomes a five-minute patrol.
- All 472 terrain-catalogue airfields and helipads are available for explicit selection. Client spawn airbases have blue-coalition ownership and unlimited ammunition and fuel in their mission warehouses. Ground starts require compatible parking; fixed-wing aircraft require a runway. Helicopters can return to helicopter-only bases.
- Fortified lines use varied offsets, headings, alternating depth, and `Sandbag_01` cover. Facility strikes create two to four separated occupied sites with fuel, command, ammunition, factory, or radar roles, logistics vehicles, guards, and themed supplies. There is at most one giant workshop in a factory complex.
- Enemy CAP uses `trigger.action.activateGroup` after client takeoff and retries activation if necessary. A newly activated group must be observed alive before its absence counts as a defeat.
- Tanker and AWACS support have complete three-waypoint routes with two separated racetrack anchors, aligned spawn headings, and their correct support tasks. Only these support groups receive invisible/immortal AI commands.
- Weather supports clear, scattered, broken, overcast, rain, storm, fog, windy, and seeded random moderate conditions. The legacy `cloudy` CLI value remains an alias. Rain/storm use the legacy cloud representation so DCS precipitation is serialized; fog, visibility, and winds are explicit.
- Per-user preferences preserve theme, mission options, departure selection, and output location. Experimental downloads are manual portable EXEs; replace the file while the program is closed. The stable installer updater code is retained for its historical channel and is not invoked by the experimental app.
- The Hornet has a curated ground-attack payload with a targeting pod. Supported flyable modules use their own pylon definitions and capability-based mission choices; unarmed trainers are omitted. Generic loadouts and tanker compatibility use heuristics.
- Syria's insurgent option changes convoy and air-defense composition. Fortified-line selections and facility garrisons retain their selected regular types.
- The embedded Lua 5.1 controller provides objective status, target position, an F10 map mark, fighter activation, convoy movement, and return-to-base completion. It uses **DO SCRIPT FILE**, avoiding the `DictKey_Translation` inline-script error recorded in the original conversation. No campaign hook or changes to `MissionScripting.lua` are needed.

See [map help](MAPS.md) for optional chart calibration and supported projections.

## Reconstruction scope and provenance

The originally supplied files contained launchers and documentation, but no application source. This project reconstructs the single-mission tool described there. The [original README](original-README.md), [original requirements](original-requirements.txt), and [conversation](claudechatjames.txt) are retained as historical reference; the earlier campaign/debrief application is not this implementation.

- DCS is not installed in the cloud. Validation uses pydcs, archive inspection, and a mocked DCS Lua API. A real Windows DCS multiplayer flight remains necessary.
- Offline public coastline/lake, height/slope and approximate main-road screening is included. It is not DCS terrain or road data; buildings, obstacles and units still need Mission Editor and flight checks.
- Authentic DCS imagery requires a user-supplied georeferenced chart.
- Historical campaign persistence, forward FARPs, dedicated WWII force sets, and prop-size calibration have not been reconstructed. Helicopters use friendly airfields. Germany uses a 1985 mission date; a WWII aircraft does not change the ground-force era.
- Convoy road following depends on DCS APIs, with a logged off-road fallback available. Generated loadouts should be reviewed in the simulator.

Syria and Cold War Germany require their corresponding DCS map modules on the pilots' machines. See [VALIDATION.md](VALIDATION.md) for the test record and remaining in-simulator checks.
