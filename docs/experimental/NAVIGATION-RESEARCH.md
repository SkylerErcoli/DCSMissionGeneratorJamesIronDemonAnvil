# Target assistance and navigation

Reviewed public primary sources on **2026-10-18** after expanded network access became available. These describe documented features, not independent flight testing. No third-party code or assets were copied.

| Source | Documented feature | Iron Anvil decision |
| --- | --- | --- |
| [BriefingRoom: smoke designation](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/blob/main/Database/ObjectiveFeatures/TargetDesignationSmokeMarker.ini) | The player can request a target smoke marker through F10. | Add optional orange smoke on request, with an airborne teammate within 15 km and a shared five-minute cooldown. It remains blocked before recon confirms search intelligence. |
| [BriefingRoom: coordinate designation](https://github.com/DCS-BR-Tools/briefing-room-for-dcs/blob/main/Database/ObjectiveFeatures/TargetDesignationCoordinates.ini) | Target coordinates can be requested through F10. | Expand the existing live position report to include decimal degrees, DDM, DMS and native DCS MGRS. Group position, vector and smoke under Target assistance to keep the main menu short. |
| [Liberation: kneeboard generator](https://github.com/dcs-liberation/dcs_liberation/blob/develop/game/missiongenerator/kneeboard.py) | Kneeboards contain airfield, runway, ATC, navigation and support-radio information. | Add a separate legible navigation/radio page, also shown in the local browser briefing. Use only public planning points; search mode includes the approximate search center. Read home/alternate radios from the pinned pydcs catalogue. |
| [DCS smoke API](https://wiki.hoggitworld.com/view/DCS_func_smoke), [LOtoLL](https://wiki.hoggitworld.com/view/DCS_func_LOtoLL) | Native colored ground smoke and local-to-geographic coordinate conversion. | Use native sandbox APIs, terrain height and live convoy positions. Compute geographic initial bearings when conversion is available; label the grid fallback explicitly. No magnetic-bearing claim. |

The 15 km range and cooldown are our gameplay choices, not claims about another tool's implementation. This is an optional visual cue, not a simulated observer, laser designator or sensor identification. Smoke remains at its release position while convoys move. It ends through normal DCS smoke behavior; the cooldown limits request frequency, not smoke lifetime.

No new desktop settings, required mods, frameworks or mixed-aircraft packages are introduced. Cold starts are the new first-run/recommended default at the user's request; existing explicitly saved hot/air/runway starts remain valid. Runway names describe available directions rather than an ATC clearance; catalogue frequencies and actual smoke/kneeboard behavior still need a DCS flight check.
