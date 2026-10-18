# Next iteration plan — implementation authorized

Prepared 2026-10-18. **The user reset their usage limits and explicitly authorized implementation.** Current preview 5 and stable 1.2 remain untouched.

## User priorities

1. Windows portable distribution; no Linux product and no installer required.
2. Shorter iteration cycles, without repeated installer/coexistence builds.
3. Audit the friend's original requests before inventing more features.
4. Missions across substantially different eligible map areas and approach directions, with plausible placement.
5. Keep co-op setup simple, cold starts by default, and preserve stable 1.2.

## What the original material actually establishes

Sources: [original conversation](../claudechatjames.txt), [original single-mission README](../original-README.md), later user requests, and current source. The conversation ends mid-response. Original application archives/source were not supplied. An earlier AI's descriptions establish claimed behavior, not proof of a working implementation or a new instruction from the user.

| Requirement or historical claim | Current position | Next action |
| --- | --- | --- |
| Hornet co-op, GUI, client slots, shared objectives and surviving pilots returning home | Implemented, with automated checks; DCS flight validation remains outstanding. | Preserve and run representative Windows checks. |
| Varied occupied compounds, more static decoration, reduced Sndbx bunker spam, Hornet targeting pod | Multiple facility types, supporting sites, HESCO/container protection, scenery and curated Hornet pod exist. | Audit actual layouts/object counts against the specific request, not just screenshots. |
| HESCO/T-walls, varied enclosure designs, real prop-size calibration | Partial HESCO screens/container layouts exist; the full claimed wall catalogue and measured calibration workflow do not. | Record exact missing patterns; add reusable grounded layouts after geographic placement is fixed. Avoid guessed wall dimensions presented as calibrated. |
| Pod selector and laser-strike loadout mentioned at the transcript's end | Curated Hornet pod exists; no dedicated pod selector or named laser-strike choice is exposed. This was AI work narration, not a clearly separate user requirement. | Check payloads and supported pod choices; only add a simple meaningful choice if needed. |
| True/magnetic nearest-target vectors, three smoke requests per flight, spawn briefing, per-player kill debrief | Current assistance uses true/grid bearings, main/live-convoy position and team smoke cooldown; briefing/help and shared operation debrief exist. Exact earlier semantics are not all reproduced. | Identify which differences matter for this co-op tool; prioritize nearest useful target/clear progress over kill competition. Do not invent magnetic declination values. |
| Forward supplied FARPs and WWII aircraft receiving era-appropriate enemies | Advertised in original single-mission README; not reconstructed. Helicopters use airfields; WWII planes can face modern forces. | Treat as genuine functional gaps. Plan bounded era consistency first if those aircraft are used; FARP services/recovery need DCS testing. |
| Era-appropriate SEAD belt/EWR and timed CAP waves | Current defenses use a smaller selection; CAP activation is implemented, but the full advertised era/air-defense and wave system is not reproduced. | Audit unit selection and timing, then choose finite plausible opposition consistent with existing switches. |
| Campaign persistence, captured bases, economy, debrief hook/apply-turn/autoresolve | Described in early conversation; absent from current app. Later supplied README explicitly says single missions, no campaign/turns; user authorized that reconstruction. | Document as historical scope, not an automatic obligation to rebuild a campaign. Defer campaign systems. |
| Later requests: dark mode, all-map airfield selection, weather, CAP/AA switches, supplied friendly home, protected orbiting support, compounds/facility variety, sandbag lines, cold starts | Implemented in current source and automated checks. Reports of CAP/support failures still require actual DCS verification; catalogue availability is not universal aircraft/parking compatibility. | Preserve regression coverage and make a short real-flight checklist. |
| Actual DCS map imagery | Zoom/pan and online mapping exist; authentic DCS imagery requires a supplied chart. | Keep the distinction explicit. Do not claim existing mapping is DCS terrain imagery or bundle unlicensed assets. |

First implementation checkpoint should turn this preliminary audit into a concise **met / partial / missing / historical** checklist with source references and relevant tests. Avoid a large feature sweep based solely on old AI claims.

## Confirmed cause of geographic repetition

- `theatres.py` has one `default_target` and only two or three preferred blue departure bases per map.
- `generator.build_mission` starts from that target. `airfields.select_airport` chooses the closest compatible preferred blue base; other airfields are mostly manual selections/fallbacks.
- `operations.choose_target` starts toward the fixed preferred target, with just **±25°** initial heading variation. Its ordered fallback favors the same directions and distance rings.
- Classic missions at standard distance skip that target-selection step and retain the fixed default target entirely.
- Unit choices and layouts use seeded procedural randomness, with hand-authored mission rules/templates. There is no large catalogue of complete prebuilt missions, but the geographic anchors and placement rules make variations look alike. Reusing a seed or retaining a map pin also deliberately repeats a plan.

## Batch 1 — shorten delivery first

- Make the experimental release Windows-portable-first. Target a genuinely single `.exe` using a one-file bundle; test Tcl/Tk, pydcs, pyproj data, image codecs, startup/extraction and runtime Lua from a clean Windows account without Python. Do not promise standalone one-file behavior until verified.
- Remove Inno Setup, previous-installer downloads, registry checks and install/reinstall/uninstall tests from the normal experimental release path. Preserve historical installers and stable release assets.
- Keep a shareable GitHub changelog page with the portable download and checksum. No Linux application release is needed; any Linux use is only optional fast development/CI testing.
- Ordinary source checkpoints run focused tests and do not build binaries. Build Windows once when a coherent batch is ready. Replace duplicate frozen/installed probes with one meaningful portable-app probe, including persistence, upgrade-by-replacement and sample mission generation.
- Keep preferences and generated missions outside the executable/extraction directory. Replacing the EXE must preserve them. Test paths with spaces, an unwritable app folder, and launch without Python installed.
- If one-file packaging proves unreliable with native dependencies, document the evidence and use a clearly labeled portable folder ZIP rather than calling its EXE self-contained. Avoid turning packaging experiments into a long detour.

## Batch 2 — genuinely varied geography

- Introduce one shared seeded planning stage for **every mission type**, including classic standard-distance missions.
- Preserve explicit user constraints: pinned target stays fixed; chosen departure stays fixed; same seed/settings reproduce the plan; Preview and Generate share that plan. New variation chooses a fresh seed; ordinary fresh generation should not accidentally reuse an old seed unless pinned for replay.
- Automatic departure samples from compatible airfields across eligible geographic regions, rather than the nearest of a tiny fixed preferred list. Balance regions to avoid dense airport clusters dominating. Respect aircraft, client count, cold-start parking, map coverage and defined scenario/era constraints.
- Sample candidate target bearings over all eligible directions and sample a distance **range** around the selected sortie length. Use unbiased/randomized candidate ordering and bounded rejection; do not return to a single fixed anchor on failure.
- Build a spatially coherent local scenario: supplied friendly home/alternate, separated hostile objectives and staging areas, appropriate opposing airfields, and support orbits on the friendly side of the operation. Rotate/position all related sites consistently with the generated scenario. Avoid leaving enemy or support logic attached to the old map anchors.
- Use valid playable land/region polygons and footprint checks. Account for water, coastlines, nearby airfields, spacing and scenario geography. Coasts/front lines can legitimately limit headings; do not force equal direction counts where placement would be implausible.
- Add cached elevation/slope and road/land-use suitability where trustworthy licensed data is available. Ground compounds need suitable footprints; convoys need plausible road access/destinations; terrain-sensitive placement should have bounded fallback. A coarse land mask alone cannot certify DCS terrain clearance, buildings or roads. Avoid mandatory online downloads for users or shipping extracted DCS assets.
- Keep this automatic. At most add one plain choice if necessary (e.g. anywhere suitable versus chosen region), instead of another page of planning controls.

## Batch 3 — prove diversity and realism

- Before changing the sampler, generate a lightweight baseline from many seeds and plot departure/target positions and route headings per map. This diagnoses the bias quantitatively.
- Afterward, compare geographic cell coverage, compatible departure diversity, distance ranges, heading sectors, repeated coordinates, rejection/failure rates and geographic exclusions across hundreds of seeds. Use eligibility-aware checks; sparse coast/front-line geometry is not a failure of randomness by itself.
- Verify same-seed reproducibility, different-seed diversity, exact pins/departures, preview equality, cold parking, friendly supplies, hidden search intelligence and protected support. Include classic and operation missions, jets and helicopters, all three maps.
- Visually inspect a spread of generated plans/compounds, then produce a small representative Windows portable smoke set. Broad statistical planning checks should not require rendering hundreds of kneeboards or rebuilding Windows binaries.
- Real DCS flights must check a few widely separated regions, convoy roads, flat compound placement, CAP activation, support racetracks and multiplayer recovery. Record failures with seed/mission; do not call offline terrain guesses flight-verified.

## Batch 4 — close useful original gaps, then publish

Prioritize confirmed gaps relevant to the group's aircraft: plausible facilities/enclosures and weapons, appropriate era/opposition, clear objective assistance. Keep FARPs and campaign mechanics separate from the geography fix; do not add frameworks or settings just to match an old AI feature list.

Publish one coherent portable preview with a short changelog, source checkpoints, checksums and a small honest validation report. Keep `main`, stable 1.2 and all published previews immutable. Record any remaining gaps. Implementation is authorized; save progress and validation in PROGRESS.md.
