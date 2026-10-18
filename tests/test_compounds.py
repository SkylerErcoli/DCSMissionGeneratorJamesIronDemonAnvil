"""Facility checks against actual saved DCS object types and layout geometry."""
import itertools
import math
import random
import zipfile

import pytest

from dcs import Mission, lua, mapping
from ironanvil import compounds
from ironanvil.compounds import FACILITY_LABELS, build_facility_complex
from ironanvil.mapdata import is_land
from ironanvil.theatres import get_theatre


def _build(map_key="caucasus", level=2, kind="random", seed=8):
    theatre = get_theatre(map_key)
    mission = Mission(theatre.terrain())
    point = mapping.Point.from_latlng(mapping.LatLng(*theatre.default_target), mission.terrain)
    objectives, label, metadata = build_facility_complex(
        mission, mission.country("Russia"), point, random.Random(seed), level,
        facility_type=kind,
    )
    return mission, point, objectives, label, metadata


def _saved_units(mission, path):
    mission.save(str(path))
    with zipfile.ZipFile(path) as archive:
        contents = lua.loads(archive.read("mission").decode())["mission"]
    red = next(country for country in contents["coalition"]["red"]["country"].values()
               if country["name"] == "Russia")
    statics = {unit["name"]: unit for group in red["static"]["group"].values()
               for unit in group["units"].values()}
    vehicles = {group["name"]: list(group["units"].values())
                for group in red["vehicle"]["group"].values()}
    return statics, vehicles


@pytest.mark.parametrize("level, count", [(1, 2), (2, 3), (3, 4), (4, 4)])
def test_difficulty_produces_separated_occupied_sites(tmp_path, level, count):
    mission, point, objectives, _, metadata = _build(level=level)
    statics, groups = _saved_units(mission, tmp_path / "complex.miz")
    sites = metadata["sites"]
    assert len(sites) == metadata["site_count"] == count
    assert len({site["type"] for site in sites}) == count
    assert len(objectives) >= count * 2
    assert len(objectives) == len(set(objectives)) == metadata["objective_count"]
    assert all(name in statics for name in objectives)
    assert metadata["decoration_count"] >= count * 12
    for first, second in itertools.combinations(sites, 2):
        assert math.hypot(first["x"] - second["x"], first["z"] - second["z"]) >= 300
    for site in sites:
        assert math.hypot(site["x"] - point.x, site["z"] - point.y) <= 650
        assert site["decoration_count"] >= 12
        assert site["objective_count"] >= 2
        assert 2 + level <= site["garrison_units"] <= 3 + level
        occupied = [unit for name in site["vehicle_groups"] for unit in groups[name]]
        assert sum(unit["type"] == "Infantry AK" for unit in occupied) >= 2
        assert sum(unit["type"] in ("Ural-375", "Ural ATsP-6") for unit in occupied) == 2
        # Decoration occupies an area around the buildings, not one pile at the
        # objective point. The archive must contain those distinct placements.
        decor = [statics[name] for name in site["decoration_statics"]]
        assert len({(round(unit["x"], 1), round(unit["y"], 1)) for unit in decor}) == len(decor)
        assert max(unit["x"] for unit in decor) - min(unit["x"] for unit in decor) > 100
        assert max(unit["y"] for unit in decor) - min(unit["y"] for unit in decor) > 100
        assert all(math.hypot(unit["x"] - site["x"], unit["y"] - site["z"]) < 180
                   for unit in decor)


@pytest.mark.parametrize("kind, required", [
    ("fuel", {"Tank", "Tank 2"}),
    ("command", {".Command Center", "Container_office"}),
    ("ammunition", {".Ammunition depot", "Small werehouse 1"}),
    ("factory", {"Workshop A", "Garage A"}),
    ("radar", {"1L13 EWR", "Container_office"}),
])
def test_selected_primary_facility_has_correct_actual_dcs_targets(tmp_path, kind, required):
    mission, _, _, label, metadata = _build(kind=kind, level=4)
    statics, groups = _saved_units(mission, tmp_path / f"{kind}.miz")
    first = metadata["sites"][0]
    assert first["type"] == metadata["primary_type"] == kind
    assert label == FACILITY_LABELS[kind]
    assert {statics[name]["type"] for name in first["objective_statics"]} == required
    # No satellite repeats the main target, and no factory appears as a support
    # site. In particular, this must never become three giant factory buildings.
    assert all(site["type"] != kind for site in metadata["sites"][1:])
    assert all(site["type"] != "factory" for site in metadata["sites"][1:])
    assert sum(unit["type"] == "Workshop A" for unit in statics.values()) <= 1
    assert all(unit["type"] not in {"Bunker", "Sandbox", "outpost", "outpost_road"}
               for unit in statics.values())
    allowed = {"Ural-375", "Ural ATsP-6", "Infantry AK", "BMP-2"}
    assert {unit["type"] for group in groups.values() for unit in group} <= allowed
    if kind == "radar":
        radar = next(statics[name] for name in first["objective_statics"] if statics[name]["type"] == "1L13 EWR")
        assert radar["category"] == "Vehicles"
        assert radar["name"] in first["objective_statics"]


def test_container_yard_has_four_regular_boundaries_with_vehicle_gate(tmp_path):
    mission, _, _, _, metadata = _build(kind="ammunition", seed=13)
    statics, _ = _saved_units(mission, tmp_path / "yard.miz")
    site = metadata["sites"][0]
    radians = math.radians(site["heading"])

    def local(unit):
        dx, dz = unit["x"] - site["x"], unit["y"] - site["z"]
        return (dx * math.cos(radians) + dz * math.sin(radians),
                -dx * math.sin(radians) + dz * math.cos(radians))

    length = 12.192
    boundary = [statics[name] for name in site["decoration_statics"] if "container boundary" in name]
    assert len(boundary) == 62  # 18+18+14+14 containers, two removed at the gate.
    sides = {"top": [], "bottom": [], "left": [], "right": []}
    for unit in boundary:
        assert unit["type"] == "Container_40ft"
        x, z = local(unit)
        if math.isclose(z, 7 * length, abs_tol=.001):
            sides["top"].append(x)
        elif math.isclose(z, -7 * length, abs_tol=.001):
            sides["bottom"].append(x)
        elif math.isclose(x, -9 * length, abs_tol=.001):
            sides["left"].append(z)
        elif math.isclose(x, 9 * length, abs_tol=.001):
            sides["right"].append(z)
        else:
            pytest.fail(f"Boundary container is off its side: {x}, {z}")
    assert {side: len(values) for side, values in sides.items()} == {
        "top": 18, "bottom": 16, "left": 14, "right": 14,
    }
    for side in ("top", "left", "right"):
        values = sorted(sides[side])
        assert all(math.isclose(b - a, length, abs_tol=.001) for a, b in zip(values, values[1:]))
    bottom = sorted(sides["bottom"])
    assert max(b - a for a, b in zip(bottom, bottom[1:])) == pytest.approx(length * 3)
    for name in site["objective_statics"]:
        x, z = local(statics[name])
        assert abs(x) < 9 * length and abs(z) < 7 * length


@pytest.mark.parametrize("map_key", ["caucasus", "syria", "germany"])
def test_all_saved_objects_and_vehicles_are_on_land_for_each_map(tmp_path, map_key):
    mission, _, _, _, metadata = _build(map_key=map_key, level=4)
    statics, groups = _saved_units(mission, tmp_path / f"{map_key}.miz")
    assert metadata["site_count"] == 4
    for unit in [*statics.values(), *(unit for group in groups.values() for unit in group)]:
        location = mapping.Point(unit["x"], unit["y"], mission.terrain).latlng()
        assert is_land(location.lat, location.lng), unit["name"]
    reloaded = Mission()
    reloaded.load_file(str(tmp_path / f"{map_key}.miz"))
    assert len(reloaded.country("Russia").static_group) == len(statics)


def test_random_selection_is_repeatable_and_includes_different_primary_facilities():
    first, _, names, label, metadata = _build(seed=47)
    second, _, repeated_names, repeated_label, repeated_metadata = _build(seed=47)
    assert (names, label, metadata) == (repeated_names, repeated_label, repeated_metadata)
    assert [group.dict() for group in first.country("Russia").static_group] == [
        group.dict() for group in second.country("Russia").static_group]
    primary_types = {_build(seed=seed, level=1)[4]["primary_type"] for seed in range(30)}
    assert primary_types == {"fuel", "command", "ammunition", "factory", "radar"}


def test_coastal_layout_relocates_sites_inland_without_piling_units(monkeypatch):
    theatre = get_theatre("caucasus")
    mission = Mission(theatre.terrain())
    point = mapping.Point.from_latlng(mapping.LatLng(*theatre.default_target), mission.terrain)
    monkeypatch.setattr(compounds, "_on_land", lambda candidate: candidate.x <= point.x + 10)
    _, _, metadata = build_facility_complex(mission, mission.country("Russia"), point,
                                            random.Random(2), 4, facility_type="fuel")
    assert metadata["site_count"] == 4
    for group in mission.country("Russia").static_group + mission.country("Russia").vehicle_group:
        assert all(unit.position.x <= point.x + 10 for unit in group.units)
    for first, second in itertools.combinations(metadata["sites"], 2):
        assert math.hypot(first["x"] - second["x"], first["z"] - second["z"]) >= 300


@pytest.mark.parametrize("kind, level", [("unknown", 2), ("fuel", 0), ("fuel", True)])
def test_invalid_request_does_not_partially_mutate_mission(kind, level):
    mission = Mission()
    with pytest.raises(ValueError):
        build_facility_complex(mission, mission.country("Russia"), mission.terrain.bounds.center(),
                               random.Random(1), level, facility_type=kind)
    assert not mission.country("Russia").static_group
    assert not mission.country("Russia").vehicle_group
