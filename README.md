# Iron Anvil Missions

A desktop generator for cooperative DCS World missions: choose **Caucasus, Syria, or Cold War Germany**, an aircraft, a mission, and **1–4 client pilots**, then generate a self-contained `.miz`.

The supplied files contained launchers and documentation, but no application source. This reconstructs the single-mission tool described there. The original README and conversation are preserved in [`docs/`](docs/); the older campaign/debrief application is historical context.

## Install and fly (Windows)

1. Install **Python 3.10 or newer**, including Tcl/Tk. Open a terminal in this folder.
2. Run `py -3 -m pip install -r requirements.txt`.
3. Double-click **`run_gui.pyw`** or run `py -3 -m ironanvil`.
4. Choose the map, aircraft, mission, client count, and target. Press **Generate mission**.
5. Open the generated mission in DCS. Windows output defaults to `Saved Games\DCS\Missions\IronAnvil` (or an existing `DCS.openbeta` folder). The output directory is configurable.

The pinned GitHub pydcs revision includes Cold War Germany; the PyPI release with the same version number does not. If an older pydcs installation wins, run **`fix_pydcs.bat`**, then **`doctor.bat`**. Use the same Python for installation and launch. `run_gui.bat` retains console errors; the `.pyw` launcher displays errors and writes `gui_error.log`.

## Target map

- Mouse wheel or **+ / −** zooms; drag to pan; **Fit map** resets the view. Click to pin a target; right-click or **Clear** removes the pin. Decimal latitude/longitude can also be entered directly.
- The offline background contains real coastlines, country boundaries, cities, coordinate grids, and airbase markers from public-domain Natural Earth data. Coastlines are coarse; choose an inland point and check local terrain in DCS.
- Enable **Internet map (OSM)** for roads, towns, and geographic detail. Visible tiles are cached locally. This is OpenStreetMap geography, **not DCS artwork**. It requires HTTPS access to `tile.openstreetmap.org`; failures fall back to the offline background.
- **Import DCS chart** overlays a local, north-up, georeferenced DCS map image. Each theatre remembers its own image. Enter its geographic bounds and projection, or provide `mychart.png.json`:

  ```json
  {"bounds": [7.0, 49.0, 17.0, 55.5], "crs": "EPSG:4326"}
  ```

  These numbers illustrate Germany bounds; they do not calibrate an arbitrary picture. Bounds are geographic degrees in **west, south, east, north** order. Supported image projections are `EPSG:4326` (equirectangular) and `EPSG:3857` (Web Mercator). A raw F10 screenshot must first be georeferenced/rectified to one of these projections. No DCS chart images were supplied; proprietary charts are not bundled or automatically extracted from DCS.

## Mission controls

**Enemy CAP flights** and **Enemy air defenses** are independent switches for **every mission type**. Turning off defenses removes enemy SAMs, AAA, MANPADS, and convoy anti-aircraft escorts, including categories selected in the fortified-line panel. With defenses off, SEAD targets command/support vehicles. With CAP off, CAP becomes a five-minute patrol near the station.

| Mission | Objective |
| --- | --- |
| Strike — facility | Destroy objective buildings inside a varied container compound with a gate and supplies. |
| Strike — fortified line | Attack a chosen unit mix in staggered, varied positions with **sandbags**, rather than concrete walls. |
| Strike — moving convoy | Intercept a convoy that starts after takeoff and attempts to use the DCS road network. F10 reports its position. |
| SEAD / DEAD | Destroy defense sites, or support vehicles when defenses are disabled. |
| CAP | Defeat enemy fighters, or patrol when enemy CAP is disabled. |

Client spawn airbases belong to the **blue coalition**, with **unlimited ammunition and fuel** in their mission warehouses, permitting friendly rearming/refueling. Ground starts, airborne starts, and return routes use a configured friendly home base.

The Hornet has a curated payload with a targeting pod for ground attack. Seventy supported flyable modules use their own pylon definitions and capability-based mission choices; unarmed trainers are omitted. Inspect and adjust generated loadouts through the rearm menu. Compatible tanker support and AWACS are optional. Difficulty, weather, time, start type, and a repeatable seed are configurable. Syria's insurgent option changes convoy and air-defense composition; fortified-line selections and facility garrisons retain their selected regular types.

The embedded **Lua 5.1** controller provides objective status, target position, an F10 map mark, fighter activation, convoy movement, and return-to-base completion. It uses **DO SCRIPT FILE**, avoiding the `DictKey_Translation` inline-script error in the chat. No campaign hook or changes to `MissionScripting.lua` are needed.

## Command line

```bat
py -3 -m ironanvil list
py -3 -m ironanvil doctor
py -3 -m ironanvil generate --map syria --aircraft FA_18C_hornet --mission line --clients 2 --line-units mbt,ifv,infantry --no-enemy-cap --no-air-defenses --seed 42
py -3 -m ironanvil generate --map germany --mission facility --target 52.55 11.4 --start hot --output my-mission.miz
```

`generate --help` lists all options; `list --json` prints a machine-readable catalogue. Linux output defaults to `~/IronAnvil/Missions`; `--output-dir` overrides it.

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

[`tools/setup_cloud.sh`](tools/setup_cloud.sh) prepares this cloud checkout with a virtual environment outside the source tree and verified Debian packages for Xvfb/Lua, without root access. Use the existing checkout: each cloud task is already isolated. [`docs/VALIDATION.md`](docs/VALIDATION.md) records validation and limits.

## Limits of this reconstruction

- DCS is not installed in the cloud. Validation uses pydcs, archive inspection, and a mocked DCS Lua API. A real Windows DCS multiplayer flight remains necessary.
- Water rejection uses coarse coastlines. There is no DCS terrain-height/slope database here; buildings and units need a final Mission Editor terrain check.
- Actual DCS imagery requires a georeferenced chart supplied by the user.
- Historical campaign persistence, forward FARPs, dedicated WWII force sets, and prop-size calibration have not been reconstructed. Helicopters use friendly airfields. Germany uses a 1985 mission date; a WWII aircraft does not change ground-force era.
- Generic loadouts and tanker compatibility are heuristic. Convoy road following depends on DCS APIs; a logged off-road fallback is available.

Syria and Cold War Germany require the corresponding DCS map modules on the pilots' machines.
