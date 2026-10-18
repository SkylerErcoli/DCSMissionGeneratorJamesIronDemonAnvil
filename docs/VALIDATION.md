# Validation and remaining checks

Validated in the cloud on 2026-10-18, using Python 3.12.14, Tk 9.0, the pinned pydcs commit, pyproj 3.7.1, Pillow 11.3.0, Xvfb, and Lua 5.1.5. **DCS itself was not run.**

| Check | Result |
| --- | --- |
| `bash tools/setup_cloud.sh` | Passed twice, including dependency consistency, doctor, and the complete test suite. Final run: **96 passed, no skips**. |
| Input/capability tests | 62 passed, including water/invalid coordinate rejection and unsupported aircraft roles. |
| Map data tests | 9 passed: coordinate transforms, zoom anchors, chart projections/persistence, cache behavior. |
| GUI tests under Xvfb | 4 passed, including every mission type and independent CAP/air-defense combinations. |
| Generator tests | 8 passed: serialized friendly warehouses, legal Hornet targeting pod, independent threat switches, sandbag/stagger geometry, enclosed compound styles, seed repeatability, atomic writes. Several tests exercise multiple generated missions. |
| Lua runtime tests in Lua 5.1 | 13 passed: objectives, fighters, CAP without enemies, convoy hold/roads/fallback, F10 reporting, air starts, multiplayer recovery, idle/late-joined clients, dead survivors, and all-client loss. |
| `python tools/test_matrix.py` | **168 missions passed, zero failed**, including pydcs reload, ZIP integrity, client counts, all three maps/four starts, friendly unlimited fuel/ammunition, coarse land placement, and embedded Lua syntax. |
| All supported aircraft | 70/70 representative build checks succeeded, using each aircraft's first supported mission, an air start, and no enemy threats. This is not every aircraft/mission/loadout combination. |
| Desktop functional check | Actual background GUI generation produced a fortified-line `.miz` with both threat switches off. Every planner tab was visually checked at the minimum window size. |
| Map functional check | Actual Tk rendering, click pinning, drag/pan, zoom, target preservation, right-click clearing, per-theatre reset, and imported chart rendering passed. |
| Packaging and preview | Wheel built with runtime Lua included; generated mission preview and overview PNGs inspected. |

The final cloud setup script was exercised in its documented working directory. It installs Python dependencies outside the checkout, obtains Xvfb and Lua through apt with Release-signature and package-hash verification, and extracts them locally without root. No package-signature, checksum, or TLS verification was disabled. Package caches and generated missions are outside tracked source or ignored.

## Requested changes verified

- Independent enemy CAP and air-defense switches reach the mission builder for all five mission types. Air defenses disabled removes SAM/AAA/MANPADS categories and convoy AA escorts. SEAD still has command/support targets; CAP without enemy fighters requires an airborne patrol.
- Every configured friendly launch airbase, including the selected home base, has BLUE ownership and unlimited fuel/ammunition in the actual saved `.miz` warehouses. Client counts and cold/hot/runway/air starts survive pydcs reload.
- Fortified lines have alternating depth, varied offsets/headings, and actual `Sandbag_01` static cover. Their cover does not use concrete walls. Facility compounds use three seeded container layouts with entry gates and supplies; bunker spam is absent.
- Joined multiplayer pilots must all recover after taking off, except lost aircraft. The first pilot landing cannot complete a mission while another joined survivor remains airborne or idle. Success sets `IRON_ANVIL_RESULT=1`; losing all participating aircraft sets `IRON_ANVIL_RESULT=2`.

## Unverified or unavailable

- A live request to `https://tile.openstreetmap.org/6/35/20.png` returned proxy **403 Forbidden**. `tile.openstreetmap.org` was added to the saved network draft while preserving the package-manager preset. Saving the draft did not apply that policy to the running instance. Retry after saving/applying environment settings. Offline maps and local chart imports work independently.
- No actual DCS chart images were supplied. DCS chart import was tested with a georeferenced test image; authentic DCS imagery is not included. Raw F10 screenshots require georeferencing before import.
- Natural Earth coastlines are approximate and omit small lakes. They do not establish correct DCS ground elevation, slope, runway clearance, or object dimensions. Check the generated placement in the DCS Mission Editor.
- A Windows DCS multiplayer sortie remains required to verify module ownership, payload behavior, actual rearm/refuel menus, ground-object appearance, road APIs, and all simulator event behavior.
- This is a single-mission reconstruction, not the earlier campaign tool. Forward FARPs, WWII-specific force substitutions, campaign debrief persistence, and measured prop calibration remain outside its implemented scope. The historical source material is retained for reference.

The cloud configuration draft stores the tested installation script, startup/development instructions, and the optional OSM domain. Publication and validation in a newly restored task have not been performed.
