# Usability pass: evidence and decisions

Reviewed the public issue reports below on 2026-10-18. They describe specific requests or historical bugs; they are not a benchmark or evidence that current releases still have the same problems. No external code or assets were copied.

| Primary source | Reported concern | Iron Anvil decision |
| --- | --- | --- |
| [BriefingRoom #1337](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/issues/1337) | A laptop display cuts off parts of the mission brief. | Put essential choices in Quick setup, preserve scrollable customization and verify smaller windows. Keep Generate available outside the scrolling form. |
| [BriefingRoom #801](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/issues/801) | Objective entries crowd the F10 menu; a collaborator notes its limited capacity. | Remove the duplicate status entry and keep a bounded Iron Anvil menu with concise help. No menu entry per decorative object. |
| [Liberation #2137](https://github.com/dcs-liberation/dcs_liberation/issues/2137) | Labels such as SEAD/DEAD do not explain what a pilot must accomplish. | Use action descriptions in the mission picker, briefing and F10 help. State what to destroy and how recovery completes the mission. |
| [BriefingRoom #797](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/issues/797), [#138](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/issues/138) | Ambiguous default/empty loadouts; a historical Hornet strike missing its targeting pod. | Keep recommended weapons as the default, clarify the optional local-preset label and show actual loaded stores rather than implying a local preset is armed. Retain the curated Hornet pod/payload. |
| [BriefingRoom #1290](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/issues/1290) | A reproducible seed helps replay favorite missions and diagnose bad placements. | Keep saved seeds/settings and add a visible New variation action. A preview remains the plan used by Generate. |
| [RotorOps #70](https://github.com/spencershepard/RotorOps/issues/70) | Enemy skill selection was not saved/restored. | Shortcuts edit the existing persisted settings. Manual changes show Custom; loading/reopening must never silently reapply a preset. |

## Scope

This pass improves the existing shared-aircraft mission loop. It does not add campaigns, economies, external frameworks, required mods, extra aircraft roles or another tier of gameplay switches. Relaxed/Balanced/Challenging are shortcuts over existing threat and skill choices. Ground troops remain armed even when anti-air defenses are off.

First-run desktop defaults become close-to-base, daylight, clear weather, engines running in parking, precise intelligence, automatic weapons and an approved friendly alternate. Balanced ground missions omit enemy fighters while keeping ground opposition. Existing saved settings are retained. CLI defaults and portable recipe meanings stay compatible.

Research describes design inputs. Exact implementation checks and publication evidence belong in [PROGRESS.md](PROGRESS.md); real DCS flight testing remains outstanding.
