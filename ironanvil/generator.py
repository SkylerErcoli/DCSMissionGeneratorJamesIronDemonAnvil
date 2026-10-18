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
from .model import MissionOptions, resolve_aircraft
from .theatres import get_theatre


PLAYER_GROUP = "IRON ANVIL CLIENTS"
DIFFICULTY = {"easy": 1, "normal": 2, "hard": 3, "extreme": 4}
LINE_TYPES = {
    "mbt": "T-72B", "ifv": "BMP-2", "apc": "BTR-80",
    "atgm": "BRDM-2_malyutka", "infantry": "Infantry AK",
    "manpads": "SA-18 Igla manpad", "aaa": "ZSU-23-4 Shilka",
    "artillery": "SAU Msta",
}
AIR_DEFENSE_LINE_TYPES = frozenset(("manpads", "aaa"))


def default_output_dir() -> Path:
    if os.name == "nt":
        saved = Path.home() / "Saved Games"
        dcs = saved / "DCS"
        if not dcs.exists() and (saved / "DCS.openbeta").exists():
            dcs = saved / "DCS.openbeta"
        return dcs / "Missions" / "IronAnvil"
    return Path.home() / "IronAnvil" / "Missions"


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


def _friendly_base(terrain, theatre, position, aircraft, clients):
    candidates = _airports(terrain, theatre.blue_airports)
    if not candidates:
        raise ValueError(f"No configured friendly airports were found for {theatre.label}")
    # Prefer an airport which has enough compatible parking for the entire flight.
    # A runway start still uses this list for its rearm/refuel destination.
    compatible = [airport for airport in candidates
                  if len(airport.free_parking_slots(aircraft)) >= clients]
    return min(compatible or candidates, key=lambda a: a.position.distance_to_point(position))


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


def _facility(mission, country, point, rng, level):
    """Objective buildings and an uncluttered, varied static compound."""
    variants = (
        ("Command post", statics.Fortification._Command_Center),
        ("Ammunition depot", statics.Warehouse._Ammunition_depot),
        ("Fuel depot", statics.Warehouse.Tank),
        ("Factory complex", statics.Fortification.Workshop_A),
    )
    label, objective_type = rng.choice(variants)
    objectives = []
    for i in range(2 + (level > 2)):
        location = _ground_offset(point, 90, i * 75 - 40)
        objectives.append(_statics(mission, country, f"OBJECTIVE {label} {i + 1}", objective_type, location))
    # Buildings, cargo and fabric tents provide detail without bunker spam.
    decorations = (statics.Cargo.Iso_container, statics.Fortification.FARP_Tent,
                   statics.Cargo.Barrels_cargo)
    for i in range(6):
        _statics(mission, country, f"Compound supplies {i + 1}", decorations[i % len(decorations)],
                 _ground_offset(point, i * 60, 110), heading=rng.randrange(360))
    style, across, deep, partition = rng.choice((
        ("container yard", 28, 20, False),
        ("long depot", 36, 16, False),
        ("divided compound", 32, 24, True),
    ))
    # Unlike the unknown HESCO mesh lengths, a 40ft ISO container has a known
    # nominal footprint. Four complete runs contain the objective, with one
    # deliberately omitted section forming the entrance. DCS mesh alignment
    # still merits a visual check in the simulator.
    length = 12.192
    width, depth = across * length, deep * length
    def local(dx, dy):
        desired = mapping.Point(point.x + dx, point.y + dy, mission.terrain)
        return _ground_offset(point, point.heading_between_point(desired), point.distance_to_point(desired))
    for side in (-1, 1):
        for i in range(across):
            if side == -1 and i == across // 2:
                continue
            _statics(mission, country, f"Compound perimeter horizontal {side} {i}",
                     statics.Fortification.Container_40ft,
                     local(-width / 2 + (i + .5) * length, side * depth / 2), heading=0)
        for i in range(deep):
            _statics(mission, country, f"Compound perimeter vertical {side} {i}",
                     statics.Fortification.Container_40ft,
                     local(side * width / 2, -depth / 2 + (i + .5) * length), heading=90)
    if partition:
        # Separate logistics and objective yards, leaving a central passage.
        for i in range(across):
            if i in (across // 2 - 1, across // 2):
                continue
            _statics(mission, country, f"Compound partition {i}",
                     statics.Fortification.Container_40ft,
                     local(-width / 2 + (i + .5) * length, -65), heading=0)
    _statics(mission, country, "Compound gate office", statics.Fortification.Container_office,
             local(24, -depth / 2 - 12), heading=0)
    return objectives, label, style


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


def _support_flight(mission, country, name, aircraft, point, main_task, frequency):
    group = mission.flight_group_inflight(country, name, aircraft, point, 7000, 600,
                                          maintask=main_task, group_size=1)
    group.frequency = frequency
    group.points[0].tasks.append(task.OrbitAction(altitude=7000, speed=600))
    return group


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
    lines = [f"IRON ANVIL — {theatre.label}", objective,
             f"Target / CAP station: {latlng.lat:.5f}, {latlng.lng:.5f}",
             f"Home: {home.name} — BLUE coalition, unlimited fuel and ammunition.",
             "All player slots are CLIENT slots. Flight radio 251 MHz AM.",
             f"Enemy fighters: {'enabled' if options.enemy_cap else 'disabled'}. Air defences: {'enabled' if options.air_defenses else 'disabled'}.",
             "Use F10 > Iron Anvil for status and target position. Return and land at home after objectives complete.",
             f"Seed: {options.seed}; difficulty: {options.difficulty}."]
    if tanker_name:
        lines.append(f"Tanker: {tanker_name}, 251.5 MHz AM. Orbit is between home and target.")
    if options.awacs:
        lines.append("AWACS: OVERLORD, 252 MHz AM.")
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
    home = _friendly_base(terrain, theatre, target, aircraft, options.clients)
    _set_airport_ownership(terrain, theatre, home)
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
    flight.add_waypoint(target, 500 if aircraft.helicopter else 4500,
                        180 if aircraft.helicopter else 650, name="TARGET / CAP STATION")
    flight.add_runway_waypoint(home)
    mission.triggers.add_triggerzone(target, radius=1200, name="IRON ANVIL TARGET")
    approach = target.heading_between_point(home.position)
    target_groups, target_statics, cap_groups = [], [], []
    label = options.mission
    compound_style = None
    convoy = None
    convoy_destination = None
    if options.mission == "facility":
        target_statics, label, compound_style = _facility(mission, red, target, rng, level)
        _ground_group(mission, red, "FACILITY GARRISON", ["BMP-2", "Infantry AK"],
                      _ground_offset(target, 30, 180), rng, level)
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
    defense_groups = _air_defenses(mission, red, target, options, rng, level,
                                   objective=options.mission == "sead")
    if options.mission == "sead":
        target_groups.extend(defense_groups)
    if options.enemy_cap:
        enemy_type = planes.MiG_21Bis if options.map == "germany" else planes.MiG_29A
        for wave in range(1 if level < 3 else 2):
            group = mission.flight_group_inflight(red, f"ENEMY CAP {wave + 1}", enemy_type,
                        _offset(target, approach + 180, 45000 + wave * 15000),
                        6500, 800, maintask=task.CAP, group_size=1 if level == 1 else 2)
            group.late_activation = True
            group.set_skill((Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[level - 1])
            group.load_task_default_loadout(task.CAP)
            # DCS payload databases are absent on cloud machines; supply legal missiles.
            if not group.units[0].pylons:
                apply_loadout(group, "cap")
            waypoint = group.add_waypoint(target, 6500, 800, name="INTERCEPT")
            waypoint.tasks.append(task.EngageTargets(max_distance=100000, targets=[task.Targets.All.Air]))
            waypoint.tasks.append(task.OrbitAction(6500, 800, task.OrbitAction.OrbitPattern.Circle))
            cap_groups.append(group.name)
    support_position = _offset(home.position, home.position.heading_between_point(target),
                               min(40000, home.position.distance_to_point(target) * .35))
    tanker_name = None
    if options.tanker:
        tanker = tanker_type(aircraft)
        if tanker:
            tanker_name = tanker.id
            _support_flight(mission, blue, "TEXACO", tanker, support_position, task.Refueling, 251.5)
    if options.awacs:
        _support_flight(mission, blue, "OVERLORD", planes.E_3A,
                        _offset(support_position, approach + 90, 10000), task.AWACS, 252)
    if options.base_detail:
        _ground_group(mission, blue, "Home ground services", ["M 818", "M978 HEMTT Tanker"],
                      _ground_offset(home.position, 90, 700), rng, 1)
    hour = {"day": 12, "dawn": 6, "dusk": 18, "night": 0}.get(options.time_of_day, rng.randrange(24))
    mission.start_time = datetime(1985 if options.map == "germany" else 2020, 6, 15, hour, 0, 0)
    if options.weather == "cloudy":
        mission.weather.clouds_base = 2500
        mission.weather.clouds_thickness = 800
        mission.weather.clouds_density = 6
    mission.weather.wind_at_ground.speed = 2
    mission.weather.wind_at_ground.direction = rng.randrange(360)
    mission.set_sortie_text(f"Iron Anvil — {options.mission.title()} — {theatre.label}")
    briefing = _briefing(options, theatre, home, target, label, tanker_name)
    mission.set_description_text(briefing)
    mission.set_description_bluetask_text(briefing)
    config = {
        "mission_type": options.mission, "target_groups": target_groups,
        "target_statics": target_statics, "player_group": PLAYER_GROUP,
        "enemy_cap": options.enemy_cap, "cap_groups": cap_groups,
        "target": {"x": target.x, "z": target.y},
        "home": {"x": home.position.x, "z": home.position.y}, "base_name": home.name,
        "convoy_group": convoy.name if convoy else None,
        "convoy_destination": {"x": convoy_destination.x, "z": convoy_destination.y} if convoy_destination else None,
    }
    metadata = {"options": asdict(options), "home_airport": home.name, "home_airport_id": home.id,
                "target_lat": latitude, "target_lon": longitude, "runtime": config,
                "tanker": tanker_name, "compound_style": compound_style, "generator_version": 1}
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
            output_path = directory / f"IronAnvil_{options.map}_{options.mission}_{options.seed}.miz"
        path = Path(output_path).expanduser().resolve()
        if path.suffix.lower() != ".miz":
            path = path.with_suffix(".miz")
        path.parent.mkdir(parents=True, exist_ok=True)
        # A resource file avoids DCS/pydcs localized DoScript string escaping.
        with tempfile.TemporaryDirectory(prefix=".ironanvil-", dir=path.parent) as temporary:
            staged = Path(temporary) / "mission.miz"
            script = Path(temporary) / "ironanvil_runtime.lua"
            script.write_text(lua.dumps(metadata["runtime"], "IRON_ANVIL") + "\n" +
                              Path(__file__).with_name("runtime.lua").read_text(encoding="utf-8"), encoding="utf-8")
            resource = mission.map_resource.add_resource_file(script)
            trigger = triggers.TriggerStart(comment="Iron Anvil mission runtime")
            trigger.add_action(action.DoScriptFile(resource))
            mission.triggerrules.triggers.append(trigger)
            mission.save(str(staged))
            with zipfile.ZipFile(staged, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ironanvil.json", json.dumps(metadata, indent=2, sort_keys=True))
            # A failed generation leaves any previous mission intact.
            os.replace(staged, path)
        return path
    finally:
        random.setstate(state)
