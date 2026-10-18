# Iron Anvil Experimental

Co-op DCS missions for the aircraft and maps your group already owns. Everyone can fly the same aircraft type.

**[Download the Windows app and see what's changed](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.3-experimental.4)**

[Stable Iron Anvil 1.2](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0) stays unchanged and installs separately.

## Make a mission

1. Install and open **Iron Anvil Experimental**. No Python or terminal commands are needed.
2. In **Quick setup**, pick your map, aircraft, number of pilots and mission.
3. Choose **Relaxed**, **Balanced** or **Challenging**, then **Generate mission**. You can preview the plan first.
4. Open **Mission briefing**, then host the `.miz` in DCS. Friends only need DCS and the selected modules.

New installs start with a nearby target, daylight, clear weather, engines running in parking, recommended weapons and a friendly alternate. **Balanced** ground missions have air defenses and a finite ground response, with enemy fighters off. **Relaxed** removes those optional threats; ground troops remain armed. Your existing saved settings are preserved.

F10 → **Iron Anvil → Briefing / help** explains your job and how to finish. Briefed targets are marked automatically. Complete the required objective and land all surviving participating aircraft at an approved base.

## Choose your job

- **Broken Relay:** disable two fuel tanks. An optional command site can delay the ground response.
- **Supply Denial:** disable an ammunition structure. Optional fuel support can cancel the response before dispatch.
- **Rolling Thunder:** hunt moving cargo trucks. Intercept them before delivery for a bonus.
- The original facility, fortified-position, convoy, air-defense and air-patrol missions are also in the same picker.

Optional goals never block victory. Guards and scenery are not required cleanup targets. The ground response is one preplaced force, with no endless waves. If things go badly, the F10 team-withdrawal procedure lets survivors recover with partial credit.

## Adjust only what you need

The fighter and air-defense switches stay visible. **Customize** contains departure fields, weather, cold/air starts, exact coordinates, weapons, recovery choices and saved squadron presets. Irrelevant controls stay hidden. **Use recommended setup** restores the easy starting configuration while keeping your map, aircraft, pilots and pinned target.

**New variation** previews another layout without writing a mission. A preview uses the same variation as the next Generate. A map pin fixes the target location and overrides automatic distance.

Every mission includes a kneeboard and a browser briefing with goals, radios, recovery information and actual loaded stores. Optional search intelligence starts with an approximate area and a shared radio check-in; precise locations remain the default. Save/share settings or repeat a favorite mission through **Customize → Flight → Squadron presets**.

Dark/light mode, all 472 catalogued airfields/helipads, nine weather choices, friendly fuel/ammunition and protected tanker/AWACS support remain available. No extra client mods or scripting changes are required.

## Install or update

Windows 10/11, 64-bit. Run the newer experimental installer over your existing experimental copy; uninstalling first is unnecessary. It has its own settings and mission folder, and never uses the stable update feed. A portable ZIP is also available: choose **Extract All** and keep the complete folder together.

## Preview status

**This preview has not been flown in DCS.** Automated source, Lua, mission-archive and packaged Windows checks cover the generator and interface. Terrain placement, road/ground AI, damage recognition and actual multiplayer behavior still require live flights. Review a new mission in the Mission Editor before your first group sortie.

![Quick setup and mission preview](docs/experimental/images/planner.png)

[Short flying/F10 guide](docs/experimental/FLYING-TOGETHER.md) · [Community feedback behind this update](docs/experimental/USABILITY-RESEARCH.md) · [Validation and saved checkpoints](docs/experimental/PROGRESS.md) · [Research roadmap](docs/experimental/README.md) · [Source development](docs/DEVELOPMENT.md)
