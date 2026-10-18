# Experimental work log and resume point

Stable invariants: leave `main`, tag `v1.2.0`, stable release downloads and its updater untouched. Work and push only `experimental`. No DCS installation is available here; record simulator checks as outstanding.

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
