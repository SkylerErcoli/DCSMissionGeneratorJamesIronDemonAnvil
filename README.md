# Iron Anvil Experimental

Create DCS co-op missions for your friends: choose the map and aircraft you own, pick a job, and generate a mission.

**[Windows EXE download and changelog](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.4.1-experimental.7)** · [Stable 1.2 remains available](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0)

**1.4.1 fixes the DCS missing locked-time errors for tanker, AWACS and enemy CAP.** Replace the EXE, then generate a new mission. Existing `.miz` files need a separate repair or regeneration.

## Run it

1. Download **IronAnvil-Experimental.exe**, save it in a folder you like, and double-click it. No installer, ZIP extraction or Python is required.
2. In **Quick setup**, choose Caucasus, Syria or Cold War Germany, your shared aircraft, pilot count and mission.
3. Choose **Preview mission on map**, then **Generate mission**. Open **Mission briefing** for the job, radios and loaded weapons.
4. Host the saved `.miz` in DCS. Only the mission creator needs this app; friends join normally with the selected DCS aircraft and map modules.

Windows 10/11, 64-bit. The EXE is unsigned, so Windows may show an unrecognized publisher prompt.

New installs start parked with **engines off**, nearby targets, daylight, clear weather, recommended weapons and a friendly alternate. **Balanced** ground missions have air defenses and one finite ground response, with enemy fighters off. **Relaxed** removes those optional threats; ground troops remain armed. Existing saved preferences stay intact. **Use recommended setup** applies these defaults to an existing copy.

## A different location each sortie

Automatic planning varies suitable departure airfields, target regions, directions and distances across the map. It screens coastlines, lakes, approximate elevation/slope and space for related sites. Convoys use approximate main-road corridors, then DCS chooses its actual road route. The offline relief map shows public terrain and major roads without an internet connection. It is not DCS terrain imagery.

Preview and Generate use the same variation. After generating an automatic preview, the next Generate chooses a fresh variation. **New variation** previews another layout. A manually entered or imported seed stays fixed for replay and is labeled **Fixed variation**. A map pin stays where you put it and overrides automatic target distance.

Your chosen job still matters: **Broken Relay** is a fuel strike; **Facility strike** randomizes fuel, command, ammunition, factory or radar facilities. Layouts and placements are generated procedurally around those mission rules.

![Offline terrain and a generated cooperative mission](docs/experimental/images/planner.png)

## Fly together

In DCS, **F10 → Iron Anvil → Briefing / help** repeats your objectives and recovery instructions. Joining pilots also get a private briefing. Required and optional sites have distinct marks; optional search intelligence initially shows an approximate area.

**Target assistance** provides live coordinates, bearings and optional orange ground-target smoke. Smoke needs a confirmed target and an airborne teammate within 15 km; the team shares a five-minute cooldown. It does not laser-designate targets. Convoys may move away from released smoke.

Complete the required job and recover all surviving participating aircraft at home or the approved alternate. **Team withdrawal** lets the group agree to recover early for partial credit. Guards and scenery do not block the cooperative operations' functional objectives.

**Customize** contains detailed weather, departure, weapons and recovery choices, plus squadron presets and settings import/export. The [short co-op guide](docs/experimental/FLYING-TOGETHER.md) explains the three operations. No extra client mods or DCS scripting-security changes are required.

## Update

Close the program and replace your old portable EXE with the new one. Preferences and missions are stored separately and retained. If you previously used an installer, run the new downloaded EXE directly; an old Start-menu shortcut still opens the old installed version. Stable 1.2 uses separate settings and remains unchanged.

## Scope and checks

The [original-request audit](docs/experimental/ORIGINAL-REQUEST-AUDIT.md) lists implemented, partial, missing and historical campaign features. Forward FARPs, dedicated WWII forces, measured wall calibration and campaign persistence remain gaps. A WWII aircraft selection does not change ground-force era.

**Real DCS flight checks are still needed.** Public terrain/roads do not exactly match DCS buildings, trees, slopes or road networks. Inspect new locations in Mission Editor and keep the mission/variation number when reporting a problem.

[Validation and progress](docs/experimental/PROGRESS.md) · [Geography and data sources](docs/experimental/GEOGRAPHY.md) · [Developer documentation](docs/DEVELOPMENT.md)
