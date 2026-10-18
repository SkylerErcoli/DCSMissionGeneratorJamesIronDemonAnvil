# Experimental work log and resume point

Stable invariants: leave `main`, tag `v1.2.0`, stable release downloads and its updater untouched. Work and push only `experimental`. No DCS installation is available here; record simulator checks as outstanding.

**Current verified checkpoint:** [Experimental 1.4.0, preview 6](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.4.0-experimental.6), source/tag `341a13b0394ce97537ed9c0c141433385eef84a3`. Single-file Windows delivery, procedural geography, offline relief, native portable checks and independent public downloads are verified. Stable 1.2 remains the default release. The final section records current evidence; earlier sections are chronological checkpoints.

## Batch 1 — separate experimental identity

Implemented separate installer AppId, name and installation directory; separate default preferences/logs, cache and missions directories; numeric experimental version 1.3.0 and planned prerelease tag `v1.3.0-experimental.1`. Default update checks refuse the stable feed. Environment overrides remain intentional developer/test controls.

Validation: 112 existing model/preferences/updater tests passed. Additional identity guards are included. Packaging has not yet been rebuilt; the old stable Windows build script must be replaced or adapted for experimental packaging before use.

## Next batches

1. Functional cooperative objectives, optional consequences and one bounded ground response; Lua 5.1 regression tests and actual archive checks.
2. Desktop operation/distance controls, richer briefing/kneeboard, replay/presets without extra aircraft/map requirements.
3. Separate experimental Windows build and prerelease; coexistence validation beside stable 1.2.0.
4. Update this log with exact validation and any remaining limits before ending a batch.

Python: `/workspace/.venvs/ironanvil/bin/python`. For complete cloud tests prepend `/workspace/.cloud-tools/usr/bin` to PATH and run under `xvfb-run -a`. GitHub API access was restricted during earlier batches; expanded access was verified in the navigation batch. Authenticated repository pushes and workflows work. Public workflow pages and release downloads can be inspected with urllib; use a timestamp query to avoid stale cached status.

## Batch 2 — functional cooperative operations

Implemented `broken_relay` and `supply_denial` profiles in `operations.py`, a native Lua 5.1 objective/response controller in `operations.lua`, generator and CLI integration, distance-aware automatic targets, and shared recovery/debrief scoring. Required targets have explicit thresholds; optional goals delay or cancel one staged ground response before dispatch. Response routing has bounded retries and no respawn loop. Existing single-mission rules remain the default.

Validation: 24 Lua runtime cases pass, including nine new operation scenarios; 21 operation archive/model tests pass, including both profiles across every map and independent threats, four representative aircraft, pacing/pinned coordinates, reproducibility and disabled response. The earlier classic generator/compound/model/runtime set passed 105 tests. No experimental DCS flight has been performed.

Next: expose these controls in the desktop UI, then add kneeboard/replay/presets and run the complete suite. The experimental Windows build is still not ready to run; the stable build script references the old installer identity and must not be used for this branch.

## Batch 3 — usable desktop operations, briefing and replay

Desktop now defaults to Broken Relay, exposes both operations and target-distance presets, and keeps the original mission types available. Added squadron presets, portable settings import/export, replay settings from existing `.miz` files, a browser briefing, and a generated DCS kneeboard containing a route schematic, objectives, radios and cruise-only distance/time information. Imported recipes never replace this computer's output directory. The experimental header/download button is distinct and never invokes the stable updater.

Validation: complete source suite **318 passed, no skips**, under Xvfb/Lua 5.1. Actual operation archives reload on all maps; recipe import is bounded and never executes mission scripts. The desktop was visually checked at 1300x700. The generated kneeboard/briefing is included in the mission, so players need no extra software. Real DCS flight and kneeboard display remain unverified.

Next: experimental Windows packaging/coexistence and a prerelease. Do not run the old stable build script on this branch.

## Batch 4 — experimental Windows prerelease pipeline

Added a dedicated Windows build/coexistence script and `experimental-release.yml`. The pipeline checks the source and Lua, generates the classic 168-mission matrix, builds and probes the experimental portable/installed programs, installs the verified published 1.2.0 sibling, checks stable executable/settings and mission preservation, reinstalls the experimental copy without a directory override, removes it, and actually runs the stable executable afterward. Publication is explicitly a prerelease with `--latest=false`, its own asset names and tag. The stable build script now refuses experimental source.

Preflight: complete source suite **319 passed**, followed by the expanded **25-case Lua suite** (one additional staging-mark case). Source executable probe passed **55 generated/reloaded missions**, including **12 operation cases**, **55 decoded kneeboards**, local briefing and replay checks. Desktop probe covers both themes/all maps and persistent operation/distance/response settings. Workflow YAML and documentation links were checked. These are source checks; Windows packaging/coexistence results are pending the new workflow run.

Resume instructions: inspect the newest Experimental co-op preview workflow after pushing this batch. If it fails, inspect its public summary, fix and commit on `experimental`; never modify `main` or replace a published tag. After success, download the experimental installer/ZIP/checksums and all six JSON reports, verify hashes and ZIP integrity, check the stable latest manifest still reports 1.2.0, and record exact URLs/results here. Real DCS playtesting remains outstanding.

## Batch 4 completed — published and independently verified

- Release: [first co-op experimental preview](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.0-experimental.1), built from `11d05f8`.
- [CI run 39119538322](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39119538322) passed Linux, Windows and publication. Linux includes the full source/Lua suite and 168-mission matrix.
- Actual frozen and installed Windows apps each passed **55 generated/reloaded missions**, including 12 operation cases and 55 decoded kneeboards, plus six map/theme renders and persistent operation settings.
- Actual coexistence/reinstall/uninstall report passed. Published stable 1.2.0 was SHA-256-verified, installed separately, retained its executable and preferences bytes, and passed its own **43-mission frozen self-test after experimental uninstall**. An existing mission and experimental preferences were retained.
- Independently downloaded the public installer (**21,969,935 bytes**) and ZIP (**30,447,728 bytes**), checksums and all six JSON reports. Both hashes matched. All **1,356 ZIP members** passed integrity checks, including the operation Lua resource and experimental handout. Every executable/coexistence report confirms success.
- Verified GitHub `/releases/latest` and its `update.json` still point to **1.2.0**. `main` remains `62e5dd42408b138f126655dbff9dbf78f73b03c6`; tag `v1.2.0` remains `04820cf9448d804c0d3ad8fff12dc15bb741783a`.

All implementation batches are committed and pushed to `experimental`. The app is a **prerelease**, deliberately excluded from the stable update feed. No further source changes are pending at this checkpoint.

## Next work after this checkpoint

1. Fly both operations in DCS with at least two players, initially with CAP/air defenses off. Check static damage thresholds, stage holding/dispatch, road routing, optional-target consequences, kneeboard display and all-survivor recovery. Repeat across the supported maps before calling the preview flight-tested.
2. Record pacing and terrain-placement problems with the mission seed/settings. Tune the finite response using observed playtests; current timings are initial game rules.
3. Candidate next gameplay batch: convoy interception with consequences, reconnaissance/search, an optional return-with-partial-result command, and better alternate-base recovery. Keep a single shared aircraft type as the default; mixed-aircraft packages, rescue logistics and campaigns remain later options.
4. For a new binary, increment `RELEASE_TAG` and corresponding workflow/notes/download links (and numeric app version as appropriate). **Never replace the existing preview's assets/tag**, merge to `main`, or change the stable updater without explicit direction.
5. The default experimental updater is intentionally disabled; the header opens the dedicated preview page. Same-channel installers update the experimental copy in place. No external mission frameworks or dependencies were added.

## Continued creative development — batch 5

The first preview was a checkpoint, not the end of the authorized experimental work. Development continues on `experimental`; no environment configuration changes or approvals are needed between code batches.

Implemented Operation Rolling Thunder: three moving supply trucks with a two-truck functional threshold, optional armed escorts honoring the air-defense switch, a fuel-support bonus that can cancel the finite response, an early-interdiction bonus, and a delivery consequence that accelerates a still-preparing response without failing the mission. Native road routing and live F10 target position are reused; all pilots can keep the same aircraft.

New coverage: four Lua gameplay cases (cargo vs escorts, delivery/response, cancellation, moving position) and six actual saved/reloaded convoy operations across all maps/threat settings. Existing 25 Lua and 21 operation cases remain covered. Prerelease version is now prepared as `1.3.1` / `v1.3.1-experimental.2`; it has **not** been published. Publishing now requires a deliberate `[publish-preview]` commit checkpoint or workflow dispatch; ordinary feature commits continue source validation without replacing a release.

Next batches in this active work: partial-result withdrawal and alternate recovery; better operational intelligence/planning; package and upgrade-test the combined preview. Existing `v1.3.0-experimental.1` and stable `v1.2.0` remain immutable.

## Continued creative development — batch 6

Implemented optional friendly alternate recovery (actual compatible BLUE airfield with supplies), alternate vectors and briefing/kneeboard information, and a two-step F10 team withdrawal procedure. A proposal expires after 30 seconds and can be cancelled; confirmation does not finish the sortie until surviving participants recover. Safe parked teammates need not take off solely to end an aborted flight, and do not earn flight-recovery points. Incomplete operations receive proportional objective points and result flag 3; completing the main goal during withdrawal can still earn full success. Losing all aircraft still produces failure. This is a team radio procedure, not a per-player voting mechanism.

Validation: 36 Lua cases now pass (seven new withdrawal/alternate scenarios); seven saved-recovery/input cases verify all three maps and fixed-wing/helicopter alternates, actual BLUE warehouses and supplies. The 35 GUI/recipe checks passed, including restart/import of the new options. Default recovery remains home-only and both options can be changed in the desktop or recipe. No DCS flight has been performed.

Continue directly into operational intelligence and visual planning. Publishing remains held until the combined preview is validated; no user approval or environment configuration edit is pending.

## Continued creative development — batch 7

Implemented optional search-area intelligence for ground missions. Public planning, briefing, kneeboard, F10 marks and flight waypoints withhold exact objectives until an airborne teammate spends 45 continuous seconds in the search area and requests the shared radio check-in. Enemy ground/static F10 symbols are hidden. This is an explicit intelligence game rule, not simulated sensor recognition or mission-file encryption. The team can still find and attack targets visually; confirmation grants one small shared bonus.

Added an asynchronous map preview showing home, alternate and briefed objectives or search area. Preview fixes a previously blank variation number so Generate uses the same plan; changing settings clears the plan and stale worker results are ignored. Preview writes no mission file. Nearby marker labels use separated callouts, with pan/zoom and Fit mission controls retained.

Validation: **85 focused GUI/recipe/intelligence/Lua checks passed**, including 39 Lua scenarios, search archives on all three maps, absence of exact target coordinates from public briefings, actual saved hidden symbols/search waypoints, asynchronous preview-to-generated-plan equality, stale-result handling and nearby label readability. The worst-case search/alternate/support kneeboard was visually checked and fits its page. Combined Windows packaging, actual old-preview upgrade and full regression validation are next; no new binary is published at this checkpoint.

## Continued creative development — batch 8 release preflight

Expanded exact-app probes to **73 missions** each: 43 classic/weather/catalogue cases plus 30 operation cases, including six search missions and twelve alternate-recovery cases. Every mission includes a decoded kneeboard and replayable settings. Desktop probes now exercise a real asynchronous search preview and persistent intelligence/recovery/withdrawal choices as well as all six map/theme combinations. Reports include the exact version/tag.

The Windows build now downloads and SHA-256-verifies the actual published first experimental installer, installs it beside stable 1.2, upgrades it without `/DIR`, and checks preferences, mission bytes and stable executable preservation across upgrade/reinstall/uninstall. The stable executable is run again afterward. All release assets use the new immutable `v1.3.1-experimental.2` tag and never become the stable latest release.

Source preflight: full suite **359 passed, no skips**, then **46 operation/intelligence checks passed**, including twelve newly added classic-ground search privacy cases across every map and mission type. The 73-mission source executable probe and actual desktop smoke/preview/restart probe passed. The planner screenshot and player/release guides are updated. Windows and CI results remain pending this deliberate publication checkpoint; continue monitoring rather than ending at the push.

## Final review — event timing correction

An additional boundary review reproduced a scoring race: targets destroyed between the last periodic poll and final landing could be omitted from a withdrawal's final result. Recovery/loss finalization now samples operation damage immediately. A new Lua case covers full completion, bonus completion and partial damage without an intervening poll; **all 40 runtime cases pass**.

The `ce67e8e` build completed publication as `v1.3.1-experimental.2` while this correction was being tested. Its published tag/assets are left intact. The corrected build has a new numeric version **1.3.2** and immutable tag **v1.3.2-experimental.3**; its Windows upgrade baseline is now the actual published 1.3.1 installer. A simple [co-op/F10 guide](FLYING-TOGETHER.md) is committed too. Continue through final CI, independent public download checks and stable preservation verification before the next handoff.

Independently verified all public 1.3.1 downloads/checksums and six Windows reports, including its real upgrade from 1.3.0 and stable preservation. Final 1.3.2 packaging was then held at an ordinary source checkpoint for a kneeboard readability review. Closely packed convoy/delivery labels now use separated callouts; two layout regressions and an actual rendered kneeboard confirm readability. Windows product/file versions, project version, app version and release links now have a consistency check. Focused packaging/identity checks passed (8), as did intelligence/layout/packaging checks (26). The new release remains pending its final publication checkpoint.

## Final checkpoint — corrected preview published and verified

- Published [1.3.2 / experimental preview 3](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.2-experimental.3), from `913225e27c627bc5b8d7c817746b594b49a64529`. The page includes a readable changelog, the installer link, portable ZIP, checksums and six validation reports. It is explicitly a prerelease and is excluded from stable latest/update discovery.
- [CI run 39151160526](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39151160526) passed in 5m10s. Linux passed the complete **375-case** source/Lua suite and **168-mission** matrix. The runtime set includes **40 Lua 5.1 scenarios**, including the reproduced final-landing damage boundary.
- Actual frozen and installed Windows programs each passed **73 generated/reloaded missions**, including 30 operation cases, six search cases, twelve alternate-recovery cases, 73 decoded kneeboards, standalone briefings and recipe replay. Each also rendered all six map/theme combinations, ran a real asynchronous search preview, and reloaded intelligence/recovery/withdrawal settings after restart. Their reports identify version 1.3.2 and the correct release tag.
- Actual Windows installation checks SHA-256-verified the published 1.3.1 experimental baseline, upgraded it without `/DIR`, retained its custom installation path and preferences, and reinstalled the new preview. Stable 1.2 executable/preferences and an existing mission stayed byte-for-byte unchanged across upgrade/reinstall/uninstall. After experimental uninstall, the real stable executable passed its **43-mission** self-test again.
- Independently downloaded the public installer (**21,991,965 bytes**), ZIP (**30,467,744 bytes**), SHA-256 list and all six reports. Both hashes matched; all **1,356 ZIP members** passed integrity checks. The ZIP contains the new final-recovery sampling code, operation Lua and experimental handout. All reports passed, including actual 1.3.1-to-1.3.2 upgrade and stable preservation.
- Fresh public requests confirmed `/releases/latest` and its update manifest still report **1.2.0**. `main` remains `62e5dd42408b138f126655dbff9dbf78f73b03c6`; stable tag remains `04820cf9448d804c0d3ad8fff12dc15bb741783a`. Both older experimental tags and their published checksums are unchanged.

The source, player guide, checkpoints and publications are saved on `experimental`; this final log commit changes documentation only. No environment configuration edit, user approval, manual GitHub publication or implementation change is pending at this checkpoint.

### Next work and limits

Real DCS flight testing remains outstanding. The cloud cannot verify terrain/slope clearance, actual road following or reserve combat behavior, sensor/AI behavior, multiplayer event timing, static damage thresholds or in-simulator kneeboard display. The radio search check-in is an explicit game rule, not sensor simulation. Use the [short co-op/F10 guide](FLYING-TOGETHER.md) for a simple first flight, and retain the generated mission/settings when reporting a problem.

Next tuning should use actual co-op flights: check convoy movement/delivery and response pacing, search-area updates with late-joining clients, split home/alternate recoveries and withdrawal. Review safe placements on each map and include a helicopter sortie. Keep the single shared aircraft type and optional opposition controls. Campaign persistence, mixed-aircraft packages and external frameworks remain future proposals, not implemented features.

For any next binary, use a new numeric version and release tag, validate source/Lua and actual Windows upgrade/coexistence, then publish deliberately with `[publish-preview]`. Ordinary source checkpoints validate without publishing; never replace existing assets/tags or merge experimental work into `main` as part of this authorization.

## Usability and cleanup pass — implementation checkpoint

Reviewed seven specific public community issue reports; [sources and design decisions](USABILITY-RESEARCH.md) distinguish historical reports from current product claims. Reused and verified the existing cloud Python/Tk/Lua environment; no setup/configuration draft changes are needed. This work is the user's authorized coding task, separate from environment setup.

Implemented Quick setup and optional Customize tabs over the existing settings model, one action-based mission picker, three threat/skill shortcuts, a derived Custom indicator, sensible first-run hot/compact/day/clear defaults, and friendly alternate recovery. Existing preferences stay intact. Individual fighter/air-defense switches remain visible. Context-specific controls are hidden when irrelevant, manual coordinates are collapsed, and New variation replaces the secondary repeat action (repeat remains in saved presets). Recommended setup preserves player aircraft/map/pilots/pin/output choices; a pin visibly overrides automatic distance.

Added a concise F10 Briefing/help entry and automatic coalition-only target/search marks. Search mode keeps exact objectives hidden, required and optional marks have clear roles, and completion updates the main mark. Removed the duplicate operation-status entry, bounded the menu to nine entries, and fixed the withdrawal-status branch to explain recovery. Browser briefings lead with action-based goals and collapse technical details. Actual loaded stations/stores are recorded and an empty local preset gets a visible warning.

Validation: complete source suite **390 passed, no skips**; expanded **43 Lua scenarios** pass, including menu capacity, search mark privacy, role labels and withdrawal guidance. New GUI checks cover first-run defaults, all supported mission shortcuts, manual/custom settings across restart, fighter-only compatibility, pinned targets, 1024x700 essential controls and New variation without mission writes. Actual saved missions verify store manifests, plain-language goals, hidden search information and empty-local-preset reporting. Expanded exact-app probes (77 missions and Quick setup desktop flow) are running; Windows packaging/versioning/publication are still pending. Source feature checkpoints do not publish binaries.

## Usability release preflight

Feature checkpoint `d9bd891` is committed/pushed. Its Linux source/matrix CI passed without publishing a binary. The expanded source executable probe passed **77 generated/reloaded missions**, including 33 operation, six search, fifteen alternate, 77 store-manifest, three recommended hot-start and one local-preset case. The actual desktop probe passed Quick setup defaults, all eight mission shortcuts, the Relaxed preset, essential controls at 1024x700, all six map/theme renders, search preview and custom settings across restart. Final targeted GUI/guidance/packaging/runtime checks passed (86), with additional context-aware preset-help and packaging consistency checks passing before publication.

Prepared numeric version **1.3.3** and new tag **v1.3.3-experimental.4**, its changelog, shorter player guide/README and refreshed screenshot. The Windows pipeline now requires 77 missions plus the new Quick setup/small-window flags and upgrades from the verified published **1.3.2** installer. The installer identity, stable latest exclusion and separate data directories remain unchanged. Actual Windows packaging/public download verification is pending the deliberate publication checkpoint; continue through those checks before handoff.


## Usability checkpoint completed — 1.3.3 published and independently verified

- Release: [Experimental 1.3.3, preview 4](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.3-experimental.4), source/tag `9ac55d096aa95bb9cf4fab342dd864c1f8b81bcd`. The public changelog and installer link are verified; publication is a prerelease with `--latest=false`.
- [CI run 39155920287](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39155920287) passed Linux, Windows and publication in **4m44s**. Linux ran the full **390-case** source/Lua suite and **168-mission** matrix. The native Lua set now has **43 scenarios**.
- The actual frozen and installed Windows apps each passed **77 generated/reloaded missions**, including 33 operation cases, six search cases, fifteen alternate-recovery cases, 77 actual store-manifest comparisons, three recommended hot-start missions and one local-preset case. Every archive includes the kneeboard, local briefing, replay settings and concise radio-help data.
- Both actual Windows desktop probes passed Quick setup/defaults, all eight mission shortcuts, the Relaxed preset, essential controls at **1024x700**, all six map/theme renders, asynchronous search preview and preservation of Custom settings across restart.
- The actual upgrade from published **1.3.2 to 1.3.3** passed without a directory override; custom installation path, preferences and existing mission bytes were preserved. Stable 1.2 executable/preferences stayed unchanged through upgrade/reinstall/uninstall, and its real executable passed **43 missions after experimental uninstall**.
- Independently downloaded the public installer (**22,005,701 bytes**), ZIP (**30,482,738 bytes**), SHA-256 list and all six reports into `/workspace/artifacts/ironanvil-v1.3.3-experimental.4`. Both hashes match; all **1,356 ZIP members** pass integrity checks. The bundled runtime contains the new help/startup marks and omits the duplicate status entry. Every public Windows report passes and identifies the correct version/tag.
- Fresh public requests confirm stable latest and its update manifest still report **1.2.0**. Stable `main`/tag and all three older experimental tags/checksum manifests are unchanged.

The source, concise player guides, research references and implementation checkpoints are committed and pushed on `experimental`. This final evidence commit changes documentation only. The existing cloud setup was reused successfully; no environment configuration or approval/publication action is pending for the user.

The next useful feedback is from actual DCS co-op flights. Defaults, readability and guidance have automated coverage; terrain clearance, roads/ground AI, damage recognition and real multiplayer behavior remain unverified in the simulator. Keep further changes focused on observed friction and the shared-aircraft mission loop. Avoid another layer of settings or adding campaign/external-framework systems to this cleanup pass. Use a new version/tag for the next binary and preserve stable 1.2 and published preview assets.


## Cold starts, target assistance and navigation — implementation checkpoint

At the user's request, first-run and recommended desktop starts now use engines-off parking. Existing saved hot/air/runway choices are retained. Verified expanded public GitHub/API access and researched BriefingRoom smoke/coordinate designation, Liberation kneeboard radios/navigation, and the native DCS API; provenance is in [NAVIGATION-RESEARCH.md](NAVIGATION-RESEARCH.md). No third-party code or assets were reused.

Implemented on-request orange smoke for confirmed ground objectives: an airborne human teammate within 15 km, shared five-minute cooldown, live convoy location and terrain height; no smoke command for CAP, no intelligence bypass, no cooldown charged on API failure. Grouped target commands keep the main radio menu bounded. Live coordinates add rounded DDM/DMS to decimal and MGRS. Vectors use geographic initial bearings where available and explicitly label true/grid rather than magnetic bearings. A second 1000×1440 kneeboard and browser navigation table contain public coordinates, catalogue home/alternate radios and runway directions. Search-only cards remain approximate. The navigation page was visually inspected with the six-point convoy plan.

Source validation passed: **410 tests**, including **49 Lua scenarios**; the application self-test generated/reloaded **77 missions**, validating every navigation page and search privacy. Desktop smoke checks passed, including cold defaults and saved hot-start preferences. The full 168-mission matrix passed. The 1.3.4 / preview 5 Windows build is next. Prior preview 4 remains the verified released checkpoint until the pipeline and independent download checks finish. No DCS flight has been performed; smoke visuals, radio catalogue accuracy, terrain, AI, kneeboards and multiplayer behavior remain unverified in the simulator.


## Navigation checkpoint completed — 1.3.4 published and independently verified

- Published [Experimental 1.3.4 / preview 5](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.4-experimental.5), source/tag `0b766083bc06f85fd8ddf00474a0ba0538d504c1`. The page has the reviewed changelog, installer link, ZIP, checksums and six Windows reports. It is a prerelease and excluded from stable latest.
- [CI run 39158819316](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39158819316) passed Linux, Windows and publication in **5m19s**. Linux passed the full **410-case** source/Lua suite and **168-mission** matrix; the runtime set has **49 Lua 5.1 scenarios**. Final review normalized recovery points into the complete vec3 required by DCS coordinate conversion and added a native-signature regression before publication. The superseded first build was canceled; its source was not published as a release.
- Actual frozen and installed Windows executables each passed **77 generated/reloaded missions**, including 33 operations, six search cases, fifteen alternate-recovery cases, 77 store manifests, **77 navigation cards**, three actual recommended cold departure routes and one local-preset case. Both 1000×1440 kneeboard pages decode; public cockpit coordinates match the planner and search cards withhold exact targets.
- Both actual Windows desktop probes passed all six map/theme renders, Quick setup defaults and mission shortcuts, Relaxed settings, essential controls at **1024×700**, asynchronous search preview and preferences across restart. A deliberately saved hot start survived the new cold default.
- The actual published **1.3.3 installer** was SHA-256 verified, installed alongside verified stable 1.2, and upgraded to **1.3.4 without /DIR**. Custom installation path, experimental preferences, existing mission bytes and stable executable/preferences were preserved through upgrade/reinstall/uninstall. After experimental uninstall, the actual stable executable again passed **43 missions**.
- Independently downloaded the public installer (**22,008,416 bytes**), ZIP (**30,486,848 bytes**), checksum list and six reports into `/workspace/artifacts/ironanvil-v1.3.4-experimental.5`. Both hashes matched; all **1,356 ZIP members** passed integrity checks. The ZIP contains version 1.3.4.0, the new target-assistance runtime including recovery vec3 normalization, and the cold-start handout. Public reports identify the correct version/tag and all required checks pass. The release body matches the reviewed notes.
- Fresh checks confirmed stable latest and `/releases/latest/download/update.json` remain **1.2.0**. `main` is still `62e5dd42408b138f126655dbff9dbf78f73b03c6`, stable tag is still `04820cf9448d804c0d3ad8fff12dc15bb741783a`, and all four previous experimental tag refs are unchanged. All **five** older published checksum manifests match their saved baselines.

No environment configuration or user publication action is pending. The existing environment was reused; expanded public network/API access was verified. Code, research, concise player guidance and release evidence are saved on `experimental`; this final checkpoint changes documentation only.

Real DCS flight testing remains outstanding, especially smoke rendering/lifetime, catalogue radio accuracy, cockpit coordinate entry, terrain/road AI, multiplayer events and actual kneeboard display. Existing missions keep their embedded controller; generate a new mission to use these additions. Preserve stable 1.2 and immutable preview tags/assets. Use a new version/tag for another binary, keep the shared-aircraft co-op workflow simple, and prefer observed flight feedback over additional settings.


## Portable/geography repair — source checkpoint

The user authorized the saved plan after resetting usage. Implemented shared procedural geography for all mission types, region-balanced compatible departures, full-circle eligible bearings and distance bands, detailed offline public land/lake/elevation screening, approximate main-road corridors, related-site fit checks, a coherent local friendly/hostile front, bounded in-map support/staging and terrain-aware client altitude handling. Added fresh automatic seed handling after Preview/Generate while retaining explicit replay seeds. Added HESCO/concrete/mixed protective screens and optional towers; sandbag fighting lines remain unchanged. Private joining-client help closes another original behavior gap. The [original-request audit](ORIGINAL-REQUEST-AUDIT.md) separates implemented, partial, missing and superseded campaign claims. [Geography notes](GEOGRAPHY.md) document data attribution, source hashes, constraints and limits.

Baseline: 300 seeds per map used one automatic departure on each map; classic standard missions used one fixed target. Initial new 1,800-plan sweep had no failures and eight heading sectors on every map. Road-aware final statistics are being recorded separately. Complete source checks passed **430 tests**, then **51 Lua scenarios** passed including new distant-road and private-join cases. The representative source executable probe passed **25 generated/reloaded missions**, with all 25 navigation cards; desktop smoke passed. A 168-mission archive/Lua matrix is finishing. These checks precede the final Windows portable build and do not establish a DCS flight.

Normal experimental packaging now targets a single Windows EXE. Removed installer builds, old installer downloads, registry/coexistence installation and duplicate installed-app probes from that release path. The native portable probe will verify a read-only app directory, paths with spaces, no Python on PATH, actual mission/GUI generation and external preferences/mission preservation when replacing the EXE. No binary is published at this source checkpoint. Stable 1.2 and published preview tags/assets remain untouched.


## Portable/geography release preflight

Source checkpoint `6de5159` is pushed and its source/Lua CI passed without building or publishing a binary. The 168-mission archive/Lua matrix completed successfully. Added the offline relief renderer and visible data credits, corrected map-footer packing on smaller windows, and made preview airfield colors match actual generated ownership. Final source/native probes check those properties explicitly. Automatic recovery plans prefer nearby alternates; an explicit isolated departure is retained with a briefing warning when a longer alternate is needed. The Sochi coastal regression now passes instead of weakening terrain screening or silently changing the departure.

Prepared **1.4.0 / v1.4.0-experimental.6**, the portable EXE workflow, player/release guides and refreshed screenshots. Final 1,800-plan report (300 seeds for classic and Rolling Thunder per map, with alternate recovery) has **zero failures** and **eight heading sectors in every map/mode**. Classic samples use **21 / 72 / 85** distinct Caucasus / Syria / Germany departures, versus one each before, and 300 distinct targets each. Operation samples use **19 / 72 / 85** departures and 300 distinct targets each. The source executable probe passes **25 missions**, navigation pages and actual airfield ownership; the desktop probe passes six terrain/theme renders, preview/restart, small-window controls and automatic/replay seeds. External saved hot-start/seed preferences are restored by the portable-state probe. Actual native Windows one-file build and public verification are still pending.


Final release preflight: **124 targeted packaging/navigation/geography/GUI/Lua tests passed** after the Sochi fix; the earlier full run had 431 passes and two Sochi failures now covered by the passing navigation regression. Final CI will run the complete exact-source suite again. Source/native-style probes pass 25 generated/reloaded missions with matching ownership and both kneeboards, six map/theme renders with offline relief, and restoration of external hot-start/seed preferences. Final screenshot and diversity comparison are saved in the player guide. Only one final Windows binary build is requested for this coherent release batch.


## Portable/geography checkpoint completed — 1.4.0 published and independently verified

- Published [Experimental 1.4.0 / preview 6](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.4.0-experimental.6), source/tag `341a13b0394ce97537ed9c0c141433385eef84a3`. Its changelog links the **single portable Windows EXE**, checksum and four native reports. There is no installer, portable-folder ZIP or Linux application asset.
- [CI run 39166970107](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/actions/runs/39166970107) passed source/Lua, native Windows and publication in **2m22s** (the previous release pipeline took 5m19s; this is an observed run comparison, not a controlled benchmark). The exact-source full suite passes; its collection has **433 tests**, including **51 Lua 5.1 scenarios**. The earlier source checkpoint also passed the **168-mission** archive/Lua matrix. The final targeted preflight passed **124 tests** after the Sochi fix.
- Native Windows ran the actual one-file executable with Python removed from PATH. It generated/reloaded **25 missions**: **18 operation**, **three search**, **nine alternate-recovery**, three recommended cold-start and one local-preset case. All 25 have matching actual stores, ownership/navigation and both decoded kneeboards. The actual desktop rendered all **six map/theme combinations** with bundled relief, checked 1024×700 controls, ran asynchronous preview and restored settings across restart.
- A real deny-write ACL made the program directory read-only; a write attempt was rejected before the executable probes ran. The portable app worked from that directory and paths with spaces. After replacing the EXE, a separate real desktop launch restored external hot-start/seed/unknown-marker preferences, and an existing mission stayed unchanged. The application folder contained **exactly one entry**, the EXE. No installer, registry migration or previous-release downloads were used. This is replacement/settings compatibility proof, not a claim of executing every old version or every possible preferences migration.
- Independently downloaded **IronAnvil-Experimental.exe (44,336,580 bytes)**, checksum and all four reports into `/workspace/artifacts/ironanvil-v1.4.0-experimental.6`. The EXE hash matches. Independently inspected its AMD64 PE/version and **1,385 CArchive entries**, including embedded Python 3.12, all twelve map height/land/roads/relief PNGs, private welcome/runtime code and data credits. Every public report passes and identifies version/tag 1.4.0 / preview 6; the published release body matches the reviewed notes.
- Final fast planning evidence covers **1,800 plans**, with no failures, 300 unique targets per map/mode and eight heading sectors in each. Classic sampled departures are **21 Caucasus / 72 Syria / 85 Germany**, compared with one per map previously; Rolling Thunder uses **19 / 72 / 85**. Explicit pins, requested departures and replay seeds stay fixed; automatic preview seeds are released after generation. The [comparison diagram](images/geographic-diversity.png), refreshed [planner screenshot](images/planner.png), [geography notes](GEOGRAPHY.md) and [original-request audit](ORIGINAL-REQUEST-AUDIT.md) are saved.
- Stable latest and its actual `/releases/latest/download/update.json` still report **1.2.0**. Stable `main` remains `62e5dd42408b138f126655dbff9dbf78f73b03c6`; stable tag remains `04820cf9448d804c0d3ad8fff12dc15bb741783a`. All five prior experimental tag refs and all **six** older published checksum manifests match the saved baselines.

Source, data provenance, audit, player guides and proof are committed on `experimental`. No environment configuration, installer work or user publication step is pending. Ordinary source checkpoints do not build Windows; deliberate finished previews build one portable executable. Keep old published tags/assets immutable and stable 1.2 unchanged.

Remaining gaps are explicit in the audit: forward supplied FARPs, dedicated WWII forces, measured wall calibration, exact road-first runtime spawning, original magnetic/nearest-target and CAP-wave semantics, per-player kill export and historical campaign management are not all reconstructed. New screens/towers and joining briefings close focused original gaps without another settings page. Real DCS flights still need to validate terrain, roads, support AI, multiplayer events and placement. Public geography is approximate; no DCS terrain/images/meshes were extracted. Generate fresh missions for the new controller/geography and keep the mission/seed when reporting an issue.

## Reported DCS route-time save failure — 1.4.1 fix

The supplied Caucasus Supply Denial archive (seed 427909374) reproduces the screenshot's three validation errors: TEXACO and OVERLORD have no locked waypoint times; late-activated ENEMY CAP 1 also lacks a locked first waypoint. `_align_airborne_group` incorrectly unlocked every ETA. pydcs's archive reload accepts this, so earlier reload/orbit tests missed the DCS save requirement.

The helper now locks the first waypoint at ETA zero and leaves later legs speed-controlled. Regression tests first failed on the old code, then passed after the fix. Tests cover actual saved support routes on all maps/five aircraft, immediate and late CAP, both the reported mission seed and the separately exported recipe's different seed, and the native probe's rejection of missing locks, locks at the wrong point and invalid locked ETAs. User-specific output paths and attachments are not committed.

Local preflight: **441 tests passed**, with Xvfb/Lua 5.1. The source executable probe passes **25 generated missions / 71 plane and helicopter routes**, including first-point locks for late activation. A separate repaired copy of the uploaded mission changes exactly three `ETA_locked` booleans; every other parsed mission field and all nine other archive members are unchanged. ZIP integrity, Lua 5.1 compilation and pydcs reload pass. No attached Lua is executed.

Publishing a new immutable **v1.4.1-experimental.7** portable EXE. Native Windows and independent public-download results will be recorded below after completion. Existing `.miz` files require regeneration or a separate repair; replacing the EXE cannot modify them. Real DCS launch/flight remains unverified here. Stable 1.2 and all seven prior releases remain protected.
