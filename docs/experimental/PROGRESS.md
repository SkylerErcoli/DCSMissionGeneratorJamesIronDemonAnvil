# Experimental work log and resume point

Stable invariants: leave `main`, tag `v1.2.0`, stable release downloads and its updater untouched. Work and push only `experimental`. No DCS installation is available here; record simulator checks as outstanding.

**Current verified checkpoint:** [Experimental 1.3.3, preview 4](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.3-experimental.4), source/tag `9ac55d096aa95bb9cf4fab342dd864c1f8b81bcd`. The usability cleanup, publication, actual Windows upgrade and independent public downloads are verified. Stable 1.2 remains the default release. The final section records current evidence; earlier sections are chronological checkpoints.

## Batch 1 — separate experimental identity

Implemented separate installer AppId, name and installation directory; separate default preferences/logs, cache and missions directories; numeric experimental version 1.3.0 and planned prerelease tag `v1.3.0-experimental.1`. Default update checks refuse the stable feed. Environment overrides remain intentional developer/test controls.

Validation: 112 existing model/preferences/updater tests passed. Additional identity guards are included. Packaging has not yet been rebuilt; the old stable Windows build script must be replaced or adapted for experimental packaging before use.

## Next batches

1. Functional cooperative objectives, optional consequences and one bounded ground response; Lua 5.1 regression tests and actual archive checks.
2. Desktop operation/distance controls, richer briefing/kneeboard, replay/presets without extra aircraft/map requirements.
3. Separate experimental Windows build and prerelease; coexistence validation beside stable 1.2.0.
4. Update this log with exact validation and any remaining limits before ending a batch.

Python: `/workspace/.venvs/ironanvil/bin/python`. For complete cloud tests prepend `/workspace/.cloud-tools/usr/bin` to PATH and run under `xvfb-run -a`. GitHub API is unavailable directly in this cloud; authenticated repository pushes and workflows work. Public workflow pages and release downloads can be inspected with urllib; use a timestamp query to avoid stale cached status.

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
