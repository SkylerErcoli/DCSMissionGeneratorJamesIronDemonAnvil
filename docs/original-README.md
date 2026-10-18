# Iron Anvil Missions - single-mission generator for DCS World

One click, one fresh `.miz`: pick a map, an aircraft, a mission type and 1-4 players. No campaign, no turns.
Fork of the Iron Anvil campaign tool; it reuses the compound / wall / decoration builder.

## Install (Windows, once)
1. Python 3.10+ (the standard installer includes Tkinter).
2. `pip install -r requirements.txt` - installs **pydcs from GitHub** (pinned to the tested commit) plus `pyproj`.
   The PyPI pydcs has no Cold War Germany map and no recent aircraft, so the generator needs this one.
3. Double-click `run_gui.pyw` (or `python -m ironanvil`). Missions are written to
   `Saved Games\DCS\Missions\IronAnvil\` - in DCS: Mission > My Missions > IronAnvil.

## If the window does not open
- Double-click **`doctor.bat`** (or run `python -m ironanvil doctor`). It checks Python, tkinter, pydcs, the map data and
  builds a test mission, and prints the exact error for whichever step fails.
- **`run_gui.bat`** starts the GUI in a console so any error stays on screen; **`run_gui.pyw`** now shows an error dialog
  and writes `gui_error.log` instead of failing silently.
- **"module dcs.terrain has no attribute Germany"** = you have the old PyPI pydcs. pip skips the GitHub one because both are
  version 0.15.0. Double-click **`fix_pydcs.bat`** (uninstalls pydcs, installs the pinned GitHub version), then `doctor.bat`.
- Another cause: double-clicking a `.pyw` uses a different Python than the one you ran `pip` with. Use the same one for
  both, e.g. `py -3 -m pip install -r requirements.txt` then `py -3 -m ironanvil`.

## Maps
Caucasus, Syria, Cold War Germany (West German/NATO bases vs. East German/Soviet side; 1985 date). Each has a
land mask, so nothing is spawned in the sea, and a front-line / red-airfield target list. Click the map to
pin a target; right-click clears it. On Syria you can face the regular army or insurgents (technicals, ZU-23s, Igla).

## Aircraft
Every flyable module pydcs knows (about 70 planes + helicopters), grouped by what their task lists allow:
strike missions for anything that can attack ground targets, SEAD for jets, CAP for fighters. 1-4 clients in one flight.
- **Loadouts:** F/A-18C has curated payloads (pod on station 4). Every other type gets a generated loadout built from
  its own pylon list (targeting pod / HARM targeting system, guided weapons, bombs or rockets, self-defence missiles,
  a tank). It is a sensible starting point - use the DCS rearm menu to change it. "DCS default payload" uses the
  stock payloads if pydcs can read your DCS install.
- **Tanker:** matched to the aircraft (boom KC-135, probe KC-135 MPRS, IL-78M for Russian types, KC-130 for the AV-8B);
  not offered for types that cannot refuel. **AWACS:** E-3A / A-50. Both are optional.
- **Helicopters** launch from a forward FARP (with fuel and ammo) when the nearest base is far from the target,
  and fly low-level routes. **WWII aircraft** get WWII ground forces and fighters instead of modern ones.

## Mission types
- **Strike - facility:** factory complex, command station, ammunition depot, fuel depot or radar site, inside a walled
  compound (HESCO / T-wall / container / double-ring keep / blast bays / fuel bund), defended by SAM, AAA, MANPADS,
  armour and fighters scaled by difficulty.
- **Strike - fortified line:** tanks, IFVs, APCs, ATGM carriers, infantry, MANPADS, AAA and artillery in any mix
  (tick what is present), behind wall runs, in revetment bays with fighting positions, supply and camo nets.
- **Strike - moving convoy:** spawned by the mission script on the **road network** (`land.findPathOnRoads`), escorted,
  and held until you take off. F10 menu gives its position; its last known position is also marked on the map.
  If no road route is found it falls back to a cross-country route and logs it.
- **SEAD / DEAD:** a belt of 1-4 SAM sites (era-appropriate: SA-2/3/6/8/9/13 in 1985; SA-6/8/10/11/15/19 modern),
  an early-warning radar, AAA, MANPADS and fighters.
- **CAP:** a station between your base and the front, AWACS, and waves of enemy fighters launching on a timer.
Difficulty (easy..extreme) scales defences and enemy skill. Optional: time of day, weather, start type
(cold / hot / runway / air), base detail, seed (same seed = same mission).

## Structures and decoration
Sandbox / Bunker / Outpost vehicles are limited to ONE per structure (often none). Everything else is static
objects: HESCO walls and towers, T-walls, barriers, revetments, boom-barrier gates, containers, site offices,
camo nets, tents, cargo, factory buildings and tanks.

## Calibration (do this once, or copy it from your campaign install)
The wall pieces only close up when their real lengths are known.
- **Already calibrated the campaign tool?** Copy its `ironanvil/assets/prop_sizes.json` into this folder's
  `ironanvil/assets/` - the type ids are the same, nothing to redo.
- Otherwise: `python -m ironanvil calibrate gallery` (GUI: Setup tab), load the mission in DCS, wait for the
  on-screen message, exit, then `python -m ironanvil calibrate import`.
- `python -m ironanvil calibrate report` prints the size table. Pieces that are not straight wall (aspect < 2.5) are
  skipped automatically, and each HESCO / revetment / barrier run now uses a single piece type so lengths match.
  If the HESCO walls still have gaps, send me that report.

## Command line
`python -m ironanvil list` lists aircraft and their missions.  Example:
`python -m ironanvil generate --map syria --aircraft AH_64D_BLK_II --mission line --clients 3 --line-units mbt,manpads,aaa`

## Tests (dev)
`tools/test_matrix.py` (maps x missions x aircraft x clients x start types, checks water and script validity),
`tools/test_lua.py` (runs the mission script against a mock DCS API in Lua 5.1: objectives, convoy road spawn,
menus, landing and win), `tools/test_limits.py`, `tools/preview_mission.py` (top-down picture),
`tools/build_landmask.py` (rebuild a map's land mask).

## Honest limits
- I cannot run DCS here. Everything is verified against pydcs and a mocked DCS scripting API, not in the sim.
  Check `Saved Games\DCS\Logs\dcs.log` for lines starting `IRON ANVIL` if something misbehaves.
- The convoy needs `land.findPathOnRoads` / `getClosestPointOnRoads` to behave as documented.
- FARP landing detection is by position (within 3.5 km, on the ground), not by airbase name.
- Cold War Germany needs the paid map; the generator itself does not check ownership. Modern jets are allowed there
  (anachronistic but fun); there is no era lock.
- Auto loadouts for non-Hornet types are heuristic (e.g. some stations may carry a different pod or tank than you'd pick).
