# Flying the experimental operations together

Only the person creating the mission needs Iron Anvil. Your friends join your DCS server as usual, using the selected map and aircraft modules. Everyone can fly the same aircraft type.

For an easy first try, choose **Close to base**, daylight and clear weather. Leave **Target intelligence** at precise. Turn enemy CAP and air defenses off while learning the objectives. You can turn the separate ground response off too.

Open the single portable Windows EXE; no installer or Python is needed. Start in **Quick setup**. Choose **Preview mission on map**, then **Generate mission**. Detailed choices are under **Customize**. Preview selects a variation number so the generated mission matches the plan; the next automatic Generate gets a fresh variation. Open **Mission briefing** before hosting; each pilot also gets a mission kneeboard in DCS.

## Pick a mission

| Operation | Required job | Optional choice |
| --- | --- | --- |
| Broken Relay | Destroy two of the three fuel tanks. | Destroy a command structure before the ground response dispatches to delay it by six minutes. |
| Supply Denial | Destroy an ammunition structure. | Destroy a bonus fuel tank before dispatch to cancel the ground response. |
| Rolling Thunder | Stop two of the three moving cargo trucks. | Stop them before delivery for extra points. Bonus fuel support can cancel a response that has not dispatched. |

Guards, escorts and scenery are not required cleanup targets. There is one staged ground response, with no endless reinforcement waves. A force already dispatched stays in the fight.

## Useful F10 controls

Open **F10 → Iron Anvil** in DCS's radio menu.

| Control | Use it for |
| --- | --- |
| Briefing / help | A short explanation of the actual objectives, radios and recovery rules. |
| Mission status | Check required targets, optional goals and the response state. |
| Target assistance → Target position / mark | Get decimal, DDM, DMS and MGRS coordinates and shared map marks. For a moving convoy, request again for its current position. |
| Target assistance → Smoke target (orange) | Optional visual cue for a confirmed ground target. An airborne teammate must be within 15 km; all pilots share a five-minute cooldown. Smoke stays where released as a convoy moves. This does not laser-designate the target. |
| Response staging / mark | Find the reserve force's starting area when intelligence is confirmed. |
| Vector home / alternate | Get a bearing and distance from an airborne teammate, or the first joined client if everyone is on the ground. The message names that reference pilot and identifies true bearings, or the grid fallback. These are not magnetic headings. |
| Recon check-in | Available with search-area intelligence. Keep an airborne teammate inside the search circle for 45 continuous seconds, then request the update while someone remains inside. |
| Team withdrawal | Agree over voice comms, propose withdrawal, then confirm within 30 seconds. Any teammate can cancel the proposal. |

Search mode initially gives an approximate area and hides enemy ground symbols on F10. The check-in shares target locations with the team; it is a radio-intelligence rule, not aircraft sensor recognition. You can still find and attack targets visually.

The second kneeboard page contains public target/search coordinates in cockpit-friendly formats and home/alternate ATC radios. The browser briefing has the same information. Available runway directions are not an ATC clearance. New installs start parked with engines off; **Use recommended setup** applies that default to an existing installation too.

## Finish together

After the required job is done, land every surviving participating aircraft at home. If you selected **Home or friendly alternate**, either listed base counts and has fuel/ammunition. Unlisted fields do not count as recovery bases.

If the sortie goes badly, the optional withdrawal procedure lets you recover with partial objective credit. It does not remove enemies or finish while survivors are still airborne. Completing the main job before recovery can still earn full success. Teammates who stayed parked safely at an approved base need not take off just to end a withdrawal; they receive no flight-recovery points.

The shared debrief rewards the mission and bringing pilots back, rather than competing for kills.

## If something looks wrong

This preview has automated checks but has not been flown in DCS. Check a new mission in the Mission Editor before a group flight. Roads, terrain placement, aircraft behavior and kneeboard display still need real flights.

Keep the generated `.miz` and note what happened. Its settings and variation number make the problem easier to reproduce. You can load those settings through **Import settings** or **Repeat last mission** under **Customize → Flight → Squadron presets**; exact layouts may change between program versions.

[Download and changelog](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.4.0-experimental.6) · [Stable 1.2](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0)
