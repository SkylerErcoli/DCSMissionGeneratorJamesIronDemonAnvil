"""Inspect the real saved AI routes, speeds, mission roles and weapons."""
import math
import zipfile

import pytest

from dcs import Mission, lua, planes, task
from dcs.unit import Skill

from ironanvil.air_support import create_enemy_cap, create_support_flight
from ironanvil.loadouts import pylon_choices
from ironanvil.theatres import get_theatre


def _mission_and_point(map_key="caucasus"):
    mission = Mission(get_theatre(map_key).terrain())
    airport = next(iter(mission.terrain.airports.values()))
    return mission, airport.position.point_from_heading(90, 30000)


def _tasks(point):
    return list(point["task"]["params"]["tasks"].values())


@pytest.mark.parametrize("map_key", ("caucasus", "syria", "germany"))
@pytest.mark.parametrize("aircraft,role,speed", (
    (planes.KC135MPRS, task.Refueling, 650),
    (planes.KC_135, task.Refueling, 650),
    (planes.KC130, task.Refueling, 500),
    (planes.IL_78M, task.Refueling, 650),
    (planes.E_3A, task.AWACS, 650),
))
def test_support_has_complete_level_racetrack_and_correct_serialized_speed(
        map_key, aircraft, role, speed, tmp_path):
    mission, point = _mission_and_point(map_key)
    group = create_support_flight(mission, mission.country("USA"), "SUPPORT", aircraft,
                                  point, role, 251.5, heading=67)
    destination = tmp_path / "support.miz"
    assert mission.save(str(destination))
    with zipfile.ZipFile(destination) as archive:
        saved = lua.loads(archive.read("mission").decode())["mission"]
    usa = next(country for country in saved["coalition"]["blue"]["country"].values()
               if country["name"] == "USA")
    serialized = usa["plane"]["group"][1]
    points = serialized["route"]["points"]
    unit = serialized["units"][1]
    assert len(points) == 3
    assert serialized["task"] == role.name
    assert not serialized.get("lateActivation", False)
    assert not serialized.get("uncontrolled", False)
    assert unit["speed"] == pytest.approx(speed / 3.6)
    assert unit["heading"] == pytest.approx(math.radians(67))
    assert unit["psi"] == pytest.approx(-math.radians(67))
    for waypoint in points.values():
        assert waypoint["alt_type"] == "BARO"
        assert waypoint["alt"] == unit["alt"] == 7000
        assert waypoint["speed"] == pytest.approx(speed / 3.6)
    role_id = "Tanker" if role == task.Refueling else "AWACS"
    assert any(item["id"] == role_id for item in _tasks(points[1]))
    commands = {item["params"]["action"]["id"]: item["params"]["action"]["params"]
                for item in _tasks(points[1]) if "action" in item["params"]}
    assert commands["SetInvisible"]["value"] is True
    assert commands["SetImmortal"]["value"] is True
    orbit = next(item for item in _tasks(points[2]) if item["id"] == "Orbit")
    assert orbit["params"]["pattern"] == "Race-Track"
    assert orbit["params"]["speed"] == pytest.approx(speed / 3.6)
    assert orbit["params"]["altitude"] == 7000
    assert math.hypot(points[3]["x"] - points[2]["x"],
                      points[3]["y"] - points[2]["y"]) == pytest.approx(25000)
    assert math.hypot(points[2]["x"] - points[1]["x"],
                      points[2]["y"] - points[1]["y"]) == pytest.approx(8000)
    if role == task.Refueling:
        beacon = next(item["params"]["action"]["params"] for item in _tasks(points[1])
                      if item["params"].get("action", {}).get("id") == "ActivateBeacon")
        assert (beacon["channel"], beacon["modeChannel"], beacon["unitId"]) == (11, "Y", unit["unitId"])


@pytest.mark.parametrize("aircraft", (planes.MiG_29A, planes.MiG_21Bis))
@pytest.mark.parametrize("late_activation", (True, False))
def test_cap_is_armed_and_can_engage_before_reaching_its_station(aircraft, late_activation):
    mission, station = _mission_and_point()
    spawn = station.point_from_heading(250, 45000)
    group = create_enemy_cap(mission, mission.country("Russia"), "ENEMY CAP", aircraft,
                             spawn, station, group_size=2, skill=Skill.High,
                             late_activation=late_activation)
    saved = group.dict()
    points = saved["route"]["points"]
    assert len(points) == 3
    assert saved.get("lateActivation", False) == late_activation
    assert all(unit["skill"] == "High" for unit in saved["units"].values())
    for point in points.values():
        assert point["alt_type"] == "BARO"
        assert point["alt"] == 6500
        assert point["speed"] == pytest.approx(800 / 3.6)
    engagement = next(item for item in _tasks(points[1])
                      if item["id"] == "EngageTargets" and item["params"].get("maxDistEnabled"))
    assert engagement["params"]["maxDist"] == 100000
    options = {item["params"]["action"]["params"]["name"]:
               item["params"]["action"]["params"]["value"]
               for item in _tasks(points[1])
               if item["params"].get("action", {}).get("id") == "Option"}
    assert options[task.OptROE.Key] == task.OptROE.Values.WeaponFree
    assert options[task.OptRadarUsing.Key] == task.OptRadarUsing.Values.UseForContinuousSearch
    orbit = next(item for item in _tasks(points[2]) if item["id"] == "Orbit")
    assert orbit["params"]["pattern"] == "Circle"
    assert orbit["params"]["speed"] == pytest.approx(800 / 3.6)
    choices = pylon_choices(aircraft)
    for unit in group.units:
        assert unit.pylons
        assert unit.speed == pytest.approx(800 / 3.6)
        assert unit.fuel == aircraft.fuel_max
        for number, weapon in unit.pylons.items():
            assert weapon["CLSID"] in {choice[1]["clsid"] for _, choice in choices[number]}
    protected_commands = {"SetInvisible", "SetImmortal"}
    assert not any(item["params"].get("action", {}).get("id") in protected_commands
                   for point in points.values() for item in _tasks(point))


def test_support_protection_does_not_change_client_aircraft():
    mission, point = _mission_and_point()
    create_support_flight(mission, mission.country("USA"), "TEXACO", planes.KC135MPRS,
                          point, task.Refueling, 251.5)
    client = mission.flight_group_inflight(mission.country("USA"), "CLIENTS", planes.FA_18C_hornet,
                                           point, 4500, 650, maintask=task.CAP, group_size=2)
    client.set_client()
    assert all(unit.skill == Skill.Client for unit in client.units)
    assert not any(item.params.get("action", {}).get("id") in {"SetInvisible", "SetImmortal"}
                   for waypoint in client.points for item in waypoint.tasks)


def test_support_rejects_unsupported_roles_and_obviously_unsafe_cruise_settings():
    mission, point = _mission_and_point()
    with pytest.raises(ValueError, match="Refueling or AWACS"):
        create_support_flight(mission, mission.country("USA"), "BAD", planes.E_3A,
                              point, task.CAP, 252)
    with pytest.raises(ValueError, match="does not support"):
        create_support_flight(mission, mission.country("USA"), "BAD", planes.E_3A,
                              point, task.Refueling, 252)
    with pytest.raises(ValueError, match="altitude"):
        create_support_flight(mission, mission.country("USA"), "BAD", planes.E_3A,
                              point, task.AWACS, 252, altitude=100)
    with pytest.raises(ValueError, match="speed"):
        create_support_flight(mission, mission.country("USA"), "BAD", planes.KC130,
                              point, task.Refueling, 251.5, speed_kph=700)
