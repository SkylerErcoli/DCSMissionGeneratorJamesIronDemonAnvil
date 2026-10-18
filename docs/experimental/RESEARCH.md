# Comparable DCS tools: research notes

Researched online on **2026-10-18** using the projects' public documentation. These are descriptions of documented features, not independent flight-test results. The recommendations for Iron Anvil are our design judgments. No external code or assets were incorporated during this research.

## Main comparisons

| Project and primary source | Documented focus / features | Useful lesson for Iron Anvil |
| --- | --- | --- |
| [BriefingRoom](https://github.com/DCS-BR-Tools/briefing-room-for-dcs#features-summary) | Fast single-player/co-op mission generation; player-focused scenarios; reconnaissance, designation and BDA tasks; reusable templates; era/country choices and optional scripts. | Closest product comparison. Preserve quick generation while expanding the objectives and information available to players. |
| [DCS Liberation](https://github.com/dcs-liberation/dcs_liberation#about-dcs-liberation) | External, turn-based single-player/co-op campaign generator managing a persistent combat environment. Uses pydcs, MIST and optional mission scripts. | Give individual missions consequences across sorties. A small linked operation can deliver some of that satisfaction with less management. |
| [DCS Retribution](https://github.com/dcs-retribution/dcs-retribution#about-dcs-retribution) | A separate fork of Liberation with persistent campaign management and extended features including road bases, neutral bases and additional mission types. Its documentation discusses save migration and backups. | Mixed mission packages and persistent state are valuable, but save compatibility and scenario complexity become substantial product concerns. |
| [RotorOps](https://github.com/spencershepard/RotorOps#what-is-rotorops) | Helicopter-focused mission generator and Conflict mode: progressing capture zones, moving friendly ground forces, troop transport, logistics, fixed-wing support, attack/defense roles and voiceovers. | Helicopters become central when transport and insertion affect the ground battle. Escorting an actual force creates an understandable reason to provide CAS. |
| [Leka's Foothold](https://github.com/leka1986/Lekas-Foothold#lekas-foothold) | A community evolution of the original Foothold by dzsekeb; PvE, configurable eras and forces, ranking/shop activities, customized CTLD and warehouse logistics. Documents support for all three of Iron Anvil's maps among others. | Offer useful jobs beyond destroying targets: supply, recovery and coordinated operations. Avoid introducing a large economy before the core mission loop works. |
| [DCS Olympus](https://github.com/Pax1601/DCSOlympus#what-is-this) | A mod with live map control of units, tasks and effects; coalition-limited commander modes and spawning budgets. The README says clients need no mod when used on a server; the host runs a backend and web server. | Optional human game-master play could be excellent for a group. Keep it optional because hosting is more involved than opening a `.miz`. |

BriefingRoom's original `akaAgar` repository URL redirects to the DCS-BR-Tools organization. Leka's Foothold is a later community project; its features must not be attributed wholesale to the original Foothold or to Pretense. An authoritative Pretense source was not successfully verified during this pass, so no detailed comparison relies on it.

## Frameworks that could support later experiments

| Primary source | What its documentation establishes | Integration implications |
| --- | --- | --- |
| [Dzsek's zoneCommander](https://github.com/Dzsek/zoneCommander) | Capture/upgrade/repair/destroy events, supply/patrol/attack groups, coalition support credits, rewards on recovery and persistence configuration. Its zone connections are explicitly visual, not functional supply links. | Useful model for a small objective state system. Do not assume connecting two map zones automatically simulates logistics. |
| [CTLD](https://github.com/ciribob/DCS-CTLD#features) | Radio-menu troop transport, cargo/crates, deployment of units, forward operating bases, radio beacons and JTAC support. | Evaluate a pinned optional transport integration rather than assuming DCS's base transport system covers all proposed logistics tasks. Verify extraction/FARP services per aircraft and scenario. |
| [Skynet IADS](https://github.com/walder/Skynet-IADS#abstract) | Early-warning radar sharing, coordinated SAM emissions, configurable command/power/connection nodes, HARM defense and optional simplified jamming. | Makes disabling infrastructure tactically meaningful. Requires MIST and suitable SAM group layouts; its jamming is a gameplay approximation, not a validated electronic-warfare model. |

The [Retribution README](https://github.com/dcs-retribution/dcs-retribution#special-thanks) independently documents its use of pydcs, MIST and optional MOOSE, JTAC, Skynet and artillery scripts. These projects demonstrate possibilities; they do not establish that combining those scripts with Iron Anvil will work without adaptation.

The repository's [historical changelog](https://github.com/dcs-retribution/dcs-retribution/blob/main/changelog.md) includes flight-plan, kneeboard, performance and helicopter-assault work. It also contains inherited older Liberation entries; it is not a reliable list of newly added features in today's Retribution build.

## Practical conclusions

1. **Best first investment: objectives with choices and consequences.** Iron Anvil already generates separated facilities and includes a Lua controller, so bounded changes can reuse those foundations.
2. **Keep information readable.** A shared operation status, clear success criteria and concise radio messages make complexity playable.
3. **Add roles before adding a big economy.** Mixed-flight support, convoy escort and rescue provide reasons to cooperate without a campaign spreadsheet.
4. **Use finite, understandable enemy behavior.** Reserves should start somewhere, take time to arrive, and be interruptible. Avoid unlimited waves.
5. **Budget performance early.** Olympus warns that arbitrary unit spawning can overwhelm a server. Active AI limits and cleanup are part of gameplay design.
6. **Do persistent campaigns later.** Result collection, corrupted/incomplete debriefs, save migration and dedicated-server behavior must be solved before promising reliable persistence.

## Research limits and provenance

- This review read online project documentation; it did not install or fly the comparison tools and is not a comparative reliability benchmark.
- Some DCS-hosted pages could not be reached from this environment. Verified GitHub documentation supplies the claims above. Features may change after the research date.
- Designs inspired by gameplay patterns are separate from reuse of code, voiceovers, artwork or templates. BriefingRoom and Leka's Foothold document GPL licensing; Foothold also identifies third-party components with separate or unverified permissions. Review the exact license and provenance of any component before integration.
- No dependency, plugin, paid service, server mod or scripting-security change has been added to the app as a result of this research.
