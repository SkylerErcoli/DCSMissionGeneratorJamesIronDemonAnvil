# Validation and remaining checks

Validated in the cloud and on a Windows build runner on 2026-10-18. The cloud uses Python 3.12.14, Tk 9.0, the pinned pydcs commit, pyproj 3.7.1, Pillow 11.3.0, Xvfb, and Lua 5.1.5. The released Windows app includes its own Python and Tk 8.6.15. **DCS itself was not run.**

## Windows release 1.2.0

[Windows and Linux CI run 39116741353](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39116741353) validates release commit `04820cf`. The [release](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0) adds the installer, portable ZIP, exact installer update manifest, checksums, and five executable/upgrade reports.

- Source regression suite: **269 passed, no skips**, under Xvfb with Lua 5.1 in the cloud. CI checks the source separately on Linux and Windows; Linux also generates and reloads the **168-mission matrix**.
- Every terrain-catalogue airfield/helipad is exposed: **21 Caucasus, 224 Syria, 227 Germany**. Tests cover exact explicit selection, neutral/enemy base conversion to friendly supplies, parking and helicopter-only restrictions, and helicopter return routes to bases without runways.
- Actual frozen and installed Windows executables each generate and reload **43 missions**, covering all maps, mission types, opposition switches, selected airfields, and all weather presets. Checks inspect actual serialized rain, storm, fog, visibility, winds and route tasks.
- Frozen and installed GUI checks each render **six map/theme combinations** and verify preferences reload. Independent source GUI tests exercise the actual background generation worker, persistent theme/settings, map highlighting, and update error recovery.
- The installer test downloads and SHA-256-verifies the published 1.1.0 installer, installs it into a custom path containing spaces, then runs the new installer **without a directory override**. It verifies version replacement in the same directory, unchanged preference and mission bytes, installed mission/GUI checks, and uninstall retaining user data.
- Independently downloaded the public installer (21,894,029 bytes), portable ZIP (30,369,412 bytes), manifest and all five reports. All three published SHA-256 checksums matched; all 1,355 ZIP members passed integrity checks. Every executable/upgrade report confirms success. The live updater detects 1.2.0 for a 1.1.0 caller, downloads the exact checksum-verified installer, and offers no update to a 1.2.0 caller.
- CAP regression checks use the documented `trigger.action.activateGroup`, exercise activation retries and delayed spawning, and prevent absent/unspawned fighters from counting as defeated. Support checks inspect the Tanker/AWACS role, safe cruise speeds and altitudes, two racetrack anchors 25 km apart, aligned headings, and invisible/immortal commands restricted to support aircraft.
- Normal facility missions contain three separated occupied sites; difficulty spans two to four. Tests inspect distinct themes, guards/logistics, at most one giant factory workshop, objective/decor separation and seeded repeatability. A fuel-complex preview with 109 decorative statics was visually checked.

Regenerate missions after updating: existing `.miz` files are deliberately preserved, so they keep their original routes, scripts, and targets. Automated archive/API checks do not establish in-simulator flight behavior; a Windows DCS multiplayer sortie remains required.

## Windows release 1.1.0

[Windows and Linux CI run 39113723883](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39113723883) passed for commit `80ce2a7`. The [published release](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.1.0) contains `IronAnvil-Setup-x64.exe`, `IronAnvil-Windows-x64.zip`, checksums, and validation reports.

- Source regression suite: **105 passed** in the cloud, with no skips; the CI Linux job also passed the complete suite and 168-mission matrix. Windows source tests passed separately, with Lua tests assigned to the Linux job.
- Actual frozen Windows application: **30 generated/reloaded missions** across three maps, five types, and enemy forces enabled/disabled. Confirmed the native projection database, chart image codecs/cache, friendly airport supplies, multiplayer slots, and packaged Lua resources.
- Actual frozen GUI: opened the Tk window and rendered all three maps.
- Installer: compiled successfully, performed a silent install into a path containing spaces, ran **30 more missions through the installed executable**, and uninstalled successfully. Both portable and installed probes ran outside the checkout with Python removed from PATH/PYTHONPATH/PYTHONHOME.
- Independently downloaded the public installer, ZIP, and reports. Both SHA-256 hashes matched the release checksums; the ZIP passed integrity checks and contains the x64 Windows executable, complete `_internal` runtime, and player handout. All three published executable reports confirm `ok=true`, `frozen=true`, and `platform=win32`.
- Source GUI checks exercised the real Generate button/background worker and useful DCS next-step text, checked permission-error recovery, and verified laptop-sized layout. Windows Saved Games discovery supports relocated profiles.

The installer is unsigned. The Windows executable was tested on a hosted Windows runner; a Windows DCS multiplayer sortie remains a separate in-simulator check.

## Initial reconstruction checks

| Check | Result |
| --- | --- |
| `bash tools/setup_cloud.sh` | Passed twice for the initial reconstruction, including dependency consistency, doctor, and the complete test suite. That revision: **96 passed, no skips**. Current source results are recorded above. |
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
- Fortified lines have alternating depth, varied offsets/headings, and actual `Sandbag_01` static cover. Their cover does not use concrete walls. Facility strikes now create separated occupied sites with distinct fuel, command, ammunition, factory, or radar roles, entry gates, logistics vehicles and supplies; bunker spam is absent.
- Joined multiplayer pilots must all recover after taking off, except lost aircraft. The first pilot landing cannot complete a mission while another joined survivor remains airborne or idle. Success sets `IRON_ANVIL_RESULT=1`; losing all participating aircraft sets `IRON_ANVIL_RESULT=2`.

## Unverified or unavailable

- A live request to `https://tile.openstreetmap.org/6/35/20.png` returned proxy **403 Forbidden**. `tile.openstreetmap.org` was added to the saved network draft while preserving the package-manager preset. Saving the draft did not apply that policy to the running instance. Retry after saving/applying environment settings. Offline maps and local chart imports work independently.
- No actual DCS chart images were supplied. DCS chart import was tested with a georeferenced test image; authentic DCS imagery is not included. Raw F10 screenshots require georeferencing before import.
- Natural Earth coastlines are approximate and omit small lakes. They do not establish correct DCS ground elevation, slope, runway clearance, or object dimensions. Check the generated placement in the DCS Mission Editor.
- A Windows DCS multiplayer sortie remains required to verify module ownership, payload behavior, actual rearm/refuel menus, ground-object appearance, road APIs, and all simulator event behavior.
- This is a single-mission reconstruction, not the earlier campaign tool. Forward FARPs, WWII-specific force substitutions, campaign debrief persistence, and measured prop calibration remain outside its implemented scope. The historical source material is retained for reference.

The cloud configuration draft stores the tested installation script, startup/development instructions, and the optional OSM domain. Its setup recipe was validated in this workspace; applying that saved configuration in a newly restored environment remains a separate check.
