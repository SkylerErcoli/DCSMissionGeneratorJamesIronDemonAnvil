"""Build self-contained DCS single missions with the pinned pydcs library."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import random
import tempfile
import zipfile

from dcs import Mission, mapping, planes, statics, task, triggers, action, vehicles
from dcs.mission import StartType
from dcs.unit import Skill
from dcs import lua

from .loadouts import apply_loadout, tanker_type
from .model import MissionOptions, resolve_aircraft, default_output_dir
from .theatres import get_theatre
from .airfields import select_airport, select_alternate
from .weather import apply_weather, WEATHER_LABELS
from .air_support import create_support_flight, create_enemy_cap
from .compounds import build_facility_complex
from .operations import build_operation, choose_target, operation_briefing
from . import APP_DATA_NAME, __version__
from .planning import search_intelligence, planner_metadata


PLAYER_GROUP = "IRON ANVIL CLIENTS"
DIFFICULTY = {"easy": 1, "normal": 2, "hard": 3, "extreme": 4}
LINE_TYPES = {
    "mbt": "T-72B", "ifv": "BMP-2", "apc": "BTR-80",
    "atgm": "BRDM-2_malyutka", "infantry": "Infantry AK",
    "manpads": "SA-18 Igla manpad", "aaa": "ZSU-23-4 Shilka",
    "artillery": "SAU Msta",
}
AIR_DEFENSE_LINE_TYPES = frozenset(("manpads", "aaa"))


def _vehicle(identifier):
    return vehicles.vehicle_map[identifier]


def _offset(point, heading, distance):
    return point.point_from_heading(heading % 360, distance)


def _ground_offset(point, heading, distance):
    from .mapdata import is_land
    for fraction in (1, .75, .5, .25, 0):
        location = _offset(point, heading, distance * fraction)
        coordinates = location.latlng()
        if is_land(coordinates.lat, coordinates.lng):
            return location
    return point


def _airports(terrain, names):
    result = []
    for name in names:
        airport = terrain.airports.get(name)
        if airport is None:
            airport = next((a for a in terrain.airports.values() if a.name.lower() == name.lower()), None)
        if airport is not None:
            result.append(airport)
    return result


def _set_airport_ownership(terrain, theatre, home):
    for airport in _airports(terrain, theatre.red_airports):
        airport.set_red()
    for airport in _airports(terrain, theatre.blue_airports) + [home]:
        airport.set_blue()
        airport.unlimited_fuel = True
        airport.unlimited_munitions = True
        airport.unlimited_aircrafts = True
        airport.jet_init = airport.gasoline_init = 100
        airport.operating_level_fuel = airport.operating_level_equipment = 100


def _ground_group(mission, country, name, types, point, rng, level, heading=0):
    group = mission.vehicle_group_platoon(country, name, [_vehicle(t) for t in types], point, heading)
    skill = (Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[level - 1]
    group.set_skill(skill)
    for unit in group.units:
        unit.heading = (heading + rng.uniform(-7, 7)) % 360
    return group


def _statics(mission, country, name, static_type, point, heading=0):
    group = mission.static_group(country, name, static_type, point, heading=heading)
    return group.units[0].name


def _fortified_line(mission, country, point, approach, options, rng, level):
    requested = list(options.line_units)
    if not options.air_defenses:
        requested = [kind for kind in requested if kind not in AIR_DEFENSE_LINE_TYPES]
    # All-defence selections still produce a useful non-air-defence target.
    if not requested:
        requested = ["infantry"]
    groups = []
    count = max(6, len(requested) + level * 2)
    for i in range(count):
        kind = requested[i % len(requested)]
        # Two interleaved rows, lateral and depth jitter: no parade-ground wall.
        along = (i - (count - 1) / 2) * 48 + rng.uniform(-9, 9)
        depth = (18 if i % 2 else -22) + rng.uniform(-9, 9)
        location = _ground_offset(_ground_offset(point, approach + 90, along), approach, depth)
        group = _ground_group(mission, country, f"LINE {i + 1} {kind.upper()}",
                              [LINE_TYPES[kind]], location, rng, level, approach)
        groups.append(group.name)
        # An open rear leaves room for vehicles; these are actual sandbag IDs.
        for j, angle in enumerate((-35, 0, 35)):
            _statics(mission, country, f"Line sandbags {i + 1}-{j + 1}",
                     statics.Fortification.Sandbag_01,
                     _ground_offset(location, approach + angle, 9 + rng.uniform(-0.6, 0.6)),
                     heading=(approach + 90 + angle) % 360)
        if i % 3 == 0:
            _statics(mission, country, f"Line supply {i + 1}", statics.Cargo.Ammo_cargo,
                     _ground_offset(location, approach + 180, 15))
    return groups


def _air_defenses(mission, country, point, options, rng, level, objective=False):
    if not options.air_defenses:
        return []
    groups = []
    sites = level if objective else max(1, level - 1)
    for i in range(sites):
        p = _ground_offset(point, i * 360 / sites + 30, 700 + i * 400)
        if options.opponent == "insurgents":
            types = ["Ural-375 ZU-23 Insurgent", "Igla manpad INS"]
        elif i % 2:
            types = ["Kub 1S91 str", "Kub 2P25 ln", "Kub 2P25 ln"]
        else:
            types = ["Osa 9A33 ln"]
        group = _ground_group(mission, country, f"AIR DEFENSE SITE {i + 1}", types, p, rng, level)
        groups.append(group.name)
    if level > 1:
        group = _ground_group(mission, country, "POINT AIR DEFENSE",
                              ["SA-18 Igla manpad", "ZSU-23-4 Shilka"],
                              _ground_offset(point, 230, 280), rng, level)
        groups.append(group.name)
    return groups


def _briefing(options, theatre, home, target, label, tanker_name):
    latlng = target.latlng()
    objective = {
        "facility": f"Destroy the marked {label.lower()} objective buildings.",
        "line": "Destroy the staggered fortified line. Units have sandbag fighting positions.",
        "convoy": "Destroy the moving convoy. It moves after your flight takes off; F10 reports its current position.",
        "sead": ("Destroy all marked enemy air-defence sites." if options.air_defenses else
                 "Air defences are disabled: destroy the marked air-defence command/support vehicles."),
        "cap": ("Reach the marked CAP station and defeat the enemy fighters." if options.enemy_cap else
                "Reach the marked CAP station and patrol within 25 km for five minutes."),
    }[options.mission]
    if options.operation != "classic":
        objective = "Follow the required and bonus goals in the operation briefing. Guards and scenery are not mandatory targets."
    location_label = "Search-area center" if options.intelligence == "search" else "Target / CAP station"
    lines = [f"IRON ANVIL — {theatre.label}", objective,
             f"{location_label}: {latlng.lat:.5f}, {latlng.lng:.5f}",
             f"Home: {home.name} — BLUE coalition, unlimited fuel and ammunition.",
             "All player slots are CLIENT slots. Flight radio 251 MHz AM.",
             f"Enemy fighters: {'enabled' if options.enemy_cap else 'disabled'}. Air defences: {'enabled' if options.air_defenses else 'disabled'}.",
             "Use F10 > Iron Anvil for status and target position. Recover at an approved base after objectives complete.",
             f"Seed: {options.seed}; difficulty: {options.difficulty}."]
    if tanker_name:
        lines.append(f"Tanker: {tanker_name}, 251.5 MHz AM, TACAN 11Y TEX. Stable racetrack between home and target, 7,000 m MSL.")
    if options.awacs:
        lines.append("AWACS: OVERLORD, 252 MHz AM. Stable racetrack at 8,000 m MSL.")
    if tanker_name or options.awacs:
        lines.append("Friendly support aircraft are hidden from enemy AI targeting and protected from damage.")
    if options.loadout == "default":
        lines.append("DCS default payload selected: if no local payload was found, use the home-base rearm menu.")
    else:
        lines.append("Auto payloads outside the Hornet are heuristic; check the loadout and use the rearm menu as needed.")
    lines.append("Terrain elevation, obstacles and all in-simulator behavior require a DCS flight check.")
    return "\n\n".join(lines)


def build_mission(options: MissionOptions):
    """Return a pydcs mission and non-secret generation metadata for validation."""
    options.validate()
    rng = random.Random(options.seed)
    theatre = get_theatre(options.map)
    terrain = theatre.terrain()
    mission = Mission(terrain)
    blue = mission.country("USA")
    red = mission.country("Russia")
    aircraft = resolve_aircraft(options.aircraft)
    latitude, longitude = ((options.target_lat, options.target_lon)
                           if options.target_lat is not None else theatre.default_target)
    target = mapping.Point.from_latlng(mapping.LatLng(latitude, longitude), terrain)
    home = select_airport(terrain, theatre, target, aircraft, options.clients,
                          options.start, options.departure_airport)
    if options.target_lat is None and (options.operation != "classic" or options.pace != "standard"):
        target = choose_target(home, target, theatre, aircraft, options.pace, rng)
        coordinates = target.latlng()
        latitude, longitude = coordinates.lat, coordinates.lng
    _set_airport_ownership(terrain, theatre, home)
    alternate = select_alternate(terrain, home, target, aircraft) if options.recovery == "home_or_alternate" else None
    intelligence = search_intelligence(target, theatre, aircraft, rng) if options.intelligence == "search" else None
    navigation_target = mapping.Point(intelligence["center"]["x"], intelligence["center"]["z"], terrain) if intelligence else target
    level = DIFFICULTY[options.difficulty]
    main_task = {"cap": task.CAP, "sead": task.SEAD}.get(options.mission, task.GroundAttack)
    # Assign only a task the module advertises; some helicopters have CAS only.
    if main_task not in aircraft.tasks:
        main_task = aircraft.task_default or next(iter(aircraft.tasks))
    if options.start == "air":
        altitude = 600 if aircraft.helicopter else 4500
        flight = mission.flight_group_inflight(blue, PLAYER_GROUP, aircraft,
                    _offset(home.position, home.position.heading_between_point(target), 12000),
                    altitude, 180 if aircraft.helicopter else 650, main_task, options.clients)
    else:
        start = {"cold": StartType.Cold, "hot": StartType.Warm, "runway": StartType.Runway}[options.start]
        flight = mission.flight_group_from_airport(blue, PLAYER_GROUP, aircraft, home,
                    maintask=main_task, start_type=start, group_size=options.clients)
    flight.set_client()
    flight.frequency = 251
    apply_loadout(flight, options.mission, options.loadout)
    flight.add_waypoint(navigation_target, 500 if aircraft.helicopter else 4500,
                        180 if aircraft.helicopter else 650, name="SEARCH AREA" if intelligence else "TARGET / CAP STATION")
    mission.triggers.add_triggerzone(navigation_target, radius=intelligence["radius"] if intelligence else 1200,
                                    name="IRON ANVIL SEARCH AREA" if intelligence else "IRON ANVIL TARGET")
    approach = target.heading_between_point(home.position)
    target_groups, target_statics, cap_groups = [], [], []
    label = options.mission
    compound_style = None
    facility_metadata = None
    operation_config = None
    convoy = None
    convoy_destination = None
    if options.mission == "facility":
        if options.operation != "classic":
            operation_config, facility_metadata = build_operation(
                mission, red, target, home, theatre, options, rng, level)
            label = operation_config["title"]
            target_statics = [name for goal in operation_config["objectives"] for name in goal["statics"]]
            if operation_config.get("convoy"):
                convoy_info = operation_config["convoy"]
                convoy = mission.coalition["red"].find_group(convoy_info["group"])
                convoy_destination = mapping.Point(convoy_info["destination"]["x"], convoy_info["destination"]["z"], terrain)
        else:
            target_statics, label, facility_metadata = build_facility_complex(
                mission, red, target, rng, level, facility_type=options.facility_type)
        compound_style = facility_metadata["style"]
        for index, site in enumerate(facility_metadata["sites"], 1):
            mission.triggers.add_triggerzone(mapping.Point(site["x"], site["z"], terrain),
                radius=155, name=f"FACILITY SITE {index}: {site['type']}")
    elif options.mission == "line":
        target_groups = _fortified_line(mission, red, target, approach, options, rng, level)
    elif options.mission == "convoy":
        types = ["Ural-375", "Ural-375", "Ural ATsP-6", "BTR-80"] + ["BMP-2"] * (level - 1)
        if options.opponent == "insurgents":
            types = ["Ural-375", "BTR-60", "Ural-375"] + ["Infantry AK Ins"] * level
        if options.air_defenses:
            types.append("Ural-375 ZU-23")
        convoy = _ground_group(mission, red, "OBJECTIVE CONVOY", types, target, rng, level)
        convoy_destination = _ground_offset(target, approach + 90, 12000)
        # Runtime holds this preplaced group and replaces its route with roads.
        convoy.add_waypoint(convoy_destination, speed=30)
        target_groups.append(convoy.name)
    elif options.mission == "sead" and not options.air_defenses:
        command = _ground_group(mission, red, "OBJECTIVE AIR DEFENSE SUPPORT",
                                ["Ural-375 PBU", "ZIL-131 KUNG", "Ural-375"], target, rng, level)
        target_groups.append(command.name)
    if operation_config and not intelligence:
        for goal in operation_config["objectives"]:
            if not goal["required"]:
                flight.add_waypoint(mapping.Point(goal["position"]["x"],goal["position"]["z"],terrain),
                    500 if aircraft.helicopter else 4500,180 if aircraft.helicopter else 650,name="BONUS - OPTIONAL")
    if home.runways:
        flight.add_runway_waypoint(home)
    else:
        flight.add_waypoint(home.position,100,120,name="HOME HELIPAD")
    flight.land_at(home)
    defense_groups = _air_defenses(mission, red, target, options, rng, level,
                                   objective=options.mission == "sead")
    if options.mission == "sead":
        target_groups.extend(defense_groups)
    if options.enemy_cap:
        enemy_type = planes.MiG_21Bis if options.map == "germany" else planes.MiG_29A
        for wave in range(1 if level < 3 else 2):
            group = create_enemy_cap(mission, red, f"ENEMY CAP {wave + 1}", enemy_type,
                        _offset(target, approach + 180, 45000 + wave * 15000), target,
                        group_size=1 if level == 1 else 2,
                        skill=(Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[level - 1])
            cap_groups.append(group.name)
    support_position = _offset(home.position, home.position.heading_between_point(target),
                               min(40000, home.position.distance_to_point(target) * .35))
    tanker_name = None
    if options.tanker:
        tanker = tanker_type(aircraft)
        if tanker:
            tanker_name = tanker.id
            create_support_flight(mission, blue, "TEXACO", tanker, support_position,
                                  task.Refueling, 251.5, heading=approach + 90)
    if options.awacs:
        create_support_flight(mission, blue, "OVERLORD", planes.E_3A,
                        _offset(support_position, approach + 90, 10000), task.AWACS, 252,
                        altitude=8000, heading=approach + 90)
    if options.base_detail:
        _ground_group(mission, blue, "Home ground services", ["M 818", "M978 HEMTT Tanker"],
                      _ground_offset(home.position, 90, 700), rng, 1)
    hour = {"day": 12, "dawn": 6, "dusk": 18, "night": 0}.get(options.time_of_day, rng.randrange(24))
    mission.start_time = datetime(1985 if options.map == "germany" else 2020, 6, 15, hour, 0, 0)
    resolved_weather = apply_weather(mission, options.weather, rng)
    mission.set_sortie_text(f"Iron Anvil Experimental — {operation_config['title'] if operation_config else options.mission.title()} — {theatre.label}")
    distance_km = home.position.distance_to_point(navigation_target) / 1000
    cruise_kph = 180 if aircraft.helicopter else 650
    briefing = _briefing(options, theatre, home, navigation_target, label, tanker_name)
    if intelligence:
        briefing += (f"\n\nSEARCH-AREA INTELLIGENCE: exact objective and response coordinates are unconfirmed. "
                     f"Search radius {intelligence['radius']/1000:g} km. {intelligence['description']} "
                     "F10 Recon check-in confirms updated coordinates for the whole team. Cooperative operations award 50 shared points once. "
                     "Enemy ground groups are hidden from native F10 symbols; real sensors and visual sighting remain usable.")
    if operation_config:
        briefing = operation_briefing(operation_config) + "\n\nFLIGHT AND SUPPORT\n\n" + briefing
    briefing += f"\n\nWeather: {WEATHER_LABELS[resolved_weather]}. Surface wind {mission.weather.wind_at_ground.speed} m/s."
    briefing += (f"\n\nHome to main target: {distance_km:.1f} km / {distance_km / 1.852:.1f} NM. "
                 f"Cruise-only round trip: approximately {120 * distance_km / cruise_kph:.0f} minutes. "
                 "Excludes startup, climb, combat, weather and recovery.")
    if alternate:
        location = alternate.position.latlng()
        briefing += (f"\n\nApproved alternate recovery: {alternate.name}, {location.lat:.5f}, {location.lng:.5f}. "
                     "Friendly, with unlimited fuel and ammunition. Pilots may recover at home or this alternate. "
                     "F10 Vector alternate provides a bearing and range; the planned flight route still returns home.")
    if options.allow_withdrawal:
        briefing += ("\n\nIf the team needs to leave before the main objective is complete, use F10 Propose withdrawal, "
                     "agree over comms, then Confirm withdrawal within 30 seconds. Any teammate can cancel a proposal. "
                     "Every surviving participant must recover at an approved base for a partial debrief. "
                     "This is a team radio procedure, not a per-player voting system.")
    if facility_metadata:
        briefing += (f"\n\nFacility complex: {facility_metadata['site_count']} occupied sites, "
                     f"{facility_metadata['objective_count']} objective objects. " +
                     ("Follow the required/bonus thresholds above. " if operation_config else
                      "Destroy the primary facility and supporting sites. ") +
                     "F10 Target position marks each site.")
        if not intelligence:
            for index, site in enumerate(facility_metadata["sites"], 1):
                briefing += f"\nSite {index} ({site['type']}): {site['latitude']:.5f}, {site['longitude']:.5f}"
    mission.set_description_text(briefing)
    mission.set_description_bluetask_text(briefing)
    config = {
        "mission_type": options.mission, "target_groups": target_groups,
        "target_statics": target_statics, "player_group": PLAYER_GROUP,
        "enemy_cap": options.enemy_cap, "cap_groups": cap_groups,
        "target": {"x": target.x, "z": target.y},
        "home": {"x": home.position.x, "z": home.position.y}, "base_name": home.name,
        "recovery_bases": [{"name": airport.name, "x": airport.position.x, "z": airport.position.y}
                           for airport in ([home, alternate] if alternate else [home])],
        "recovery_label": home.name + (f" or {alternate.name}" if alternate else ""),
        "allow_withdrawal": options.allow_withdrawal,
        "intelligence": intelligence,
        "convoy_group": convoy.name if convoy else None,
        "convoy_destination": {"x": convoy_destination.x, "z": convoy_destination.y} if convoy_destination else None,
        "operation": operation_config,
        "facility_sites": [{"name": f"Site {i}: {site['type']}", "x": site["x"], "z": site["z"]}
                           for i, site in enumerate(facility_metadata["sites"], 1)] if facility_metadata else [],
    }
    if intelligence:
        for group in red.vehicle_group + red.static_group:
            group.hidden = True
    metadata = {"options": asdict(options), "home_airport": home.name, "home_airport_id": home.id,
                "intelligence": intelligence,
                "planner": planner_metadata(terrain,home,target,alternate,operation_config,intelligence),
                "target_lat": latitude, "target_lon": longitude, "runtime": config,
                "tanker": tanker_name, "compound_style": compound_style,
                "alternate_airport": alternate.name if alternate else None,
                "resolved_weather": resolved_weather, "generator_version": 3, "app_version": __version__,
                "route_summary": {"one_way_km": round(distance_km, 1),
                                  "cruise_round_trip_minutes": round(120 * distance_km / cruise_kph),
                                  "note": "Cruise-only estimate; excludes startup, climb, combat, weather and recovery."},
                "facility_type": facility_metadata["primary_type"] if facility_metadata else None,
                "facility_sites": facility_metadata["sites"] if facility_metadata else [],
                "facility_decoration_count": facility_metadata["decoration_count"] if facility_metadata else 0}
    return mission, metadata


def generate(options: MissionOptions, output_path=None) -> Path:
    """Generate a .miz file; no DCS installation or credentials are required."""
    # Some pydcs helpers use Python's module-level RNG. Preserve the caller's RNG
    # while giving identical options reproducible mission content.
    state = random.getstate()
    random.seed(options.seed)
    try:
        mission, metadata = build_mission(options)
        if output_path is None:
            directory = Path(options.output_dir).expanduser() if options.output_dir else default_output_dir()
            title = options.operation if options.operation != "classic" else options.mission
            output_path = directory / f"{APP_DATA_NAME}_{options.map}_{title}_{options.seed}.miz"
        path = Path(output_path).expanduser().resolve()
        if path.suffix.lower() != ".miz":
            path = path.with_suffix(".miz")
        path.parent.mkdir(parents=True, exist_ok=True)
        # A resource file avoids DCS/pydcs localized DoScript string escaping.
        with tempfile.TemporaryDirectory(prefix=".ironanvil-", dir=path.parent) as temporary:
            staged = Path(temporary) / "mission.miz"
            script = Path(temporary) / "ironanvil_runtime.lua"
            script.write_text(lua.dumps(metadata["runtime"], "IRON_ANVIL") + "\n" +
                              Path(__file__).with_name("operations.lua").read_text(encoding="utf-8") + "\n" +
                              Path(__file__).with_name("runtime.lua").read_text(encoding="utf-8"), encoding="utf-8")
            resource = mission.map_resource.add_resource_file(script)
            trigger = triggers.TriggerStart(comment="Iron Anvil mission runtime")
            trigger.add_action(action.DoScriptFile(resource))
            mission.triggerrules.triggers.append(trigger)
            mission.save(str(staged))
            with zipfile.ZipFile(staged, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ironanvil.json", json.dumps(metadata, indent=2, sort_keys=True))
                from .briefing import kneeboard_png, briefing_html
                kneeboard = kneeboard_png(metadata)
                archive.writestr("KNEEBOARD/IMAGES/01-IronAnvil.png", kneeboard)
                archive.writestr("ironanvil-briefing.html", briefing_html(metadata, kneeboard))
            # A failed generation leaves any previous mission intact.
            os.replace(staged, path)
        return path
    finally:
        random.setstate(state)
