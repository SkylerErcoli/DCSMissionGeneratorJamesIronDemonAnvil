# First playable experiment: Operation Broken Relay

**Design proposal, not implemented.** See the [research](RESEARCH.md) and [roadmap](README.md).

## Player experience

Generate one operation for the existing two-to-four-client flight. The briefing identifies a required fuel/logistics target, an optional communications target, and a possible enemy response from a named staging area. Both sites are available from the beginning; there is no forced waypoint order.

The group chooses to strike quickly, disable communications first for more time, or complete the main objective and withdraw. Completing the optional objective earns a bonus and changes the reinforcement timetable. The main objective can be completed without killing every guard or decorative object.

A typical run is intended to fit a 30–60-minute group session, but flight time must be estimated from the actual aircraft, departure, route and start type. If the chosen placement cannot fit the requested duration, the planner should explain that and offer a closer suitable area. It must not promise a fixed duration.

## Proposed rules

| Element | Initial proposed behavior |
| --- | --- |
| Required objective | A fuel site with three explicitly registered storage objectives. Disabling two completes the site's function. |
| Optional objective | A communications site with one explicitly registered command/communications objective. Its destruction earns the bonus. |
| Scenery and guards | Never counted toward the required fuel threshold. Guards remain a tactical threat; decorations remain scenery. |
| Enemy awareness | A scenario event starts on the first verified damage to either objective site. Describe it as an alarm/attack response, not simulated AI radar detection. |
| Response timing | Start with a three-minute dispatch delay. If communications is disabled before dispatch, add six minutes once. These are initial playtest values, not realism claims. |
| Response force | One finite ground response group, preplaced at a briefed staging area and initially held. Route toward the threatened site after dispatch. |
| Response limits | At most one dispatch, no respawn loop, no relocation to the players' position. Damage to the force remains real. |
| Late communications kill | Still earns the bonus; an already-dispatched force remains in the mission. Report that accurately. |
| Core mission result | Complete the required objective, then recover every participating surviving client under the existing rules. The optional objective never blocks mission success. |
| All-client loss | Preserve the existing failure result. Rescue/re-slot lives need a separate later design. |
| Threat switches | With enemy CAP off, no hostile fighter flight is created or dispatched. With air defenses off, neither sites nor the response force contain SAMs, AAA or MANPADS. |
| Friendly support | Retain the current protected tanker/AWACS behavior and friendly unlimited-supply home base. |
| Debrief | Show main/bonus result, response status and recovered/lost aircraft. Record the seed for replay. No persistent campaign save in this experiment. |

## Technical shape

1. **Explicit objectives in generated metadata.** Each objective needs a stable ID, role, required/optional flag, object names, completion threshold and consequence. Decoration names remain separate. Validate that thresholds are achievable and IDs/names are unique.
2. **An objective state model in the Lua controller.** Track pending/completed/failed states and one-shot consequences independently from the existing sortie-level recovery result. The optional target must not enter the legacy combined mandatory-target list.
3. **One response state model.** Track held, scheduled, dispatched, unavailable and destroyed. A scheduled activation must be idempotent. Retry transient activation failures within a defined limit; if unavailable, report that and allow normal objective/recovery completion.
4. **Correct DCS calls.** Use the existing documented activation mechanism and protected calls. The ground group needs a valid route and DCS terrain/road testing. Never infer destruction merely because a late-activated group has not yet appeared.
5. **Clear status and messages.** The F10 menu reports each objective and the response state, marks already-briefed sites, and explains the bonus effect. Announce transitions once. Avoid repeatedly printing the whole mission state.
6. **Seeded generation.** Fix site/response placement choices and timing variation with the mission seed. Log the selected values and rules in metadata so a broken mission can be reproduced.
7. **Keep the player setup simple.** Introduce one opt-in operation preset. Detailed timing and threshold tuning stays in development configuration until playtesting proves players need it.

The implementation can build on `compounds.py` for separated occupied sites, `generator.py` for metadata/configuration, and `runtime.lua` for status, activation and recovery. Do not silently change the stable facility mission's victory conditions for missions that do not opt into this mode.

## Acceptance criteria before distribution

- Main target completion works with the specified threshold while remaining scenery and guards are alive.
- Completing only the optional objective does not finish the mission. Its bonus applies once, before dispatch only, and is reported truthfully afterward.
- Main-first, optional-first and simultaneous completion produce consistent outcomes. Missing/destroyed objects and repeated events do not double-award a bonus or dispatch twice.
- Response activation failure, a delayed spawn, an unreachable route, or an early destroyed response group cannot prevent the main objective and RTB result from completing.
- CAP and air-defense switches are checked against the actual saved mission and runtime-created/activated forces.
- Generated scenarios reload through pydcs; Lua syntax and state transitions pass Lua 5.1 checks using the real documented DCS API shapes.
- Existing source and runtime regression suites pass, including protected support, home supplies, helicopter-only bases and all participating survivors recovering.
- A real two-player DCS test verifies objective damage recognition, reinforcement routing, concise messages, rearming, all-client loss, and the full return/debrief flow. Repeat on every supported map before advertising three-map support for the experiment.
- Playtest both a fast main-target strike and a communications-first strike. Record actual duration, confusing moments, dead time and active AI load. Change the initial tuning based on those observations.

## Later extensions

After this loop works, add a finite ammunition convoy whose interception cancels one later ground reinforcement; a reconnaissance mode with approximate intelligence; and a mixed-flight option for CAP/SEAD/strike. Helicopter rescue and troop capture follow as separate experiments, with their own compatible aircraft and mission-result rules.

Before distributing a binary, implement the separate experimental installation/settings/update identity described in the roadmap. The branch currently contains the stable application plus design documents; it is not an isolated experimental Windows installation yet.
