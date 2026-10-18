# Iron Anvil Missions

**Experimental branch — planning stage.** Read the [gameplay ideas, research, and proposed first experiment](docs/experimental/README.md). Experimental gameplay is not implemented yet. The [stable version 1.2.0 release](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0) remains available for normal play.

Make a DCS mission for you and your friends: choose a map, aircraft, mission, and up to four pilots, then click **Generate mission**.

## Download and open on Windows

1. **[Download the Windows installer](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/latest/download/IronAnvil-Setup-x64.exe)**.
2. Double-click **`IronAnvil-Setup-x64.exe`** and follow the short setup wizard.
3. Open **Iron Anvil** from the Start menu or its desktop shortcut.

**That's the whole setup.** The installer includes what the app needs and installs for your Windows account without administrator access. You do not need Python, a terminal, a GitHub account, or a Codex account. Use Windows 10 or 11, 64-bit.

<details>
<summary>Prefer a portable app without an installer?</summary>

Download **[IronAnvil-Windows-x64.zip](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/latest/download/IronAnvil-Windows-x64.zip)**, right-click it and choose **Extract All**, then open the extracted folder and double-click **`IronAnvil.exe`**. Keep the whole folder together, including `_internal`.

</details>

Both downloads are on the **[Downloads / Releases](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/latest)** page. GitHub's **Source code** ZIP is for developers; it is not the Windows app.

**Sharing with friends?** Send them the **[latest release and changelog](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/latest)**. It explains what changed and includes the Windows download underneath.

## Updating an existing copy

**Keep your current installation.** Run the new installer over it; it updates the same folder and keeps your missions and saved settings. You do not need to uninstall first. If you are moving from version 1.1, download this update once. Version 1.2 and later have a **Check for updates** button: it downloads and verifies the new version, then opens the upgrade wizard.

The app remembers dark/light mode, your flight settings, departure airfield, and mission output folder. Switch **Dark mode** on or off in the header.

## Make your first mission

1. Choose **Caucasus**, **Syria**, or **Cold War Germany**, your aircraft, and **1–4 pilots**. Leave the departure airfield automatic or choose one from the searchable list.
2. Pick a mission. For a facility strike, choose a fuel depot, command center, ammunition depot, factory, radar station, or random facility.
3. Choose the opposition using the two checkboxes. **Enemy CAP flights** adds enemy fighter patrols. **Enemy air defenses** adds enemy missiles and anti-aircraft guns.
4. Click the map to place the targets, or leave the target unset to have the app choose a location. Use the mouse wheel or **+ / −** to zoom, and drag to move the map.
5. Click **Generate mission**, then **Open mission folder**.
6. Open the new `.miz` mission in DCS, or use it when hosting DCS multiplayer.

Only the person creating missions needs this app. Your friends can join your DCS multiplayer server normally. Everyone flying needs their selected aircraft and any required DCS map module; Syria and Cold War Germany are separate DCS map purchases.

## What you can make

| Mission | What you do |
| --- | --- |
| Strike — facility | Attack several nearby occupied sites with varied buildings, vehicles, supplies, and clutter. |
| Strike — fortified line | Attack staggered units protected by sandbags. |
| Strike — moving convoy | Find and attack a moving convoy. |
| SEAD / DEAD | Attack enemy air defenses. With air defenses off, attack their support vehicles instead. |
| CAP | Defeat enemy fighters. With enemy CAP off, fly an unopposed patrol. |

Both opposition switches work for every mission type. Friendly starting airbases support rearming and refueling. Weather, time of day, start type, tanker support, and other options are available when you want them; you can leave the defaults for your first mission.

**All airfields:** the lists include all **472 airfields and helipads** in the supported terrain data: **21 Caucasus, 224 Syria, and 227 Cold War Germany**. Any selected launch base becomes friendly with fuel and ammunition. A helicopter-only pad cannot host a fixed-wing aircraft; parking capacity is checked for cold/hot starts, with clear guidance to change the base, pilot count, or start type.

**Weather:** clear, scattered clouds, broken clouds, overcast, rain, thunderstorms, fog, strong winds, or random flyable conditions.

**Friendly support:** tanker and AWACS fly complete racetrack orbits, are hidden from enemy AI targeting, and are protected from damage. Tanker radio is **251.5 MHz / TACAN 11Y TEX**; AWACS is **252 MHz**. Enemy CAP activates after a client takes off or joins an airborne slot.

**Facility variety:** difficulty creates two to four separated sites with different functions, parked logistics vehicles, infantry, containers, tents, equipment and supplies. Factories contain at most one main workshop building. Use **F10 → Iron Anvil → Target position / mark** to mark the individual sites. Fortified troop lines retain staggered positions and sandbag cover.

## Seeing the target area

The map works offline. Turn on **Internet map (OSM)** for more detail such as roads and towns. It shows real-world geography and can differ from DCS scenery. Zoom in, click a target, and use **Fit map** to return to the full view.

Actual DCS map artwork is not included. Importing your own DCS chart is an optional advanced feature; normal mission creation does not require it. See [map help](docs/MAPS.md) if you need it.

## If something goes wrong

- **The app will not open:** run the installer again. If you chose the portable ZIP, extract it first and keep `IronAnvil.exe` beside its `_internal` folder.
- **You cannot find the mission:** click **Open mission folder** in the app. You can also choose a different folder in its output settings.
- **The internet map does not load:** leave it off and use the offline map. Mission generation still works.
- **You want to update:** use **Check for updates**, or run the latest installer over your existing installation. For the portable app, extract the new ZIP into a new folder; saved settings and missions remain outside the app folder.

Before your first group flight, open the generated mission in the DCS Mission Editor and check the target placement and aircraft loadouts. Full flight testing in DCS remains outstanding. [Validation details](docs/VALIDATION.md) record the checks completed so far.

Developers and anyone running from source can find installation commands, command-line options, and development notes in [the development guide](docs/DEVELOPMENT.md). They are not part of the Windows app setup.
