"""Input boundaries shared by the GUI and command line."""
from dataclasses import replace
import math

import pytest

from ironanvil.model import (
    MissionOptions, aircraft_catalogue, missions_for_aircraft, resolve_aircraft,
)
from ironanvil.theatres import THEATRES, get_theatre


@pytest.mark.parametrize("map_name", tuple(THEATRES))
def test_default_target_is_on_land_inside_theatre(map_name):
    theatre = get_theatre(map_name)
    assert theatre.contains(*theatre.default_target)
    assert theatre.is_land(*theatre.default_target)
    assert MissionOptions(map=map_name).validate()


@pytest.mark.parametrize("clients", (0, 5, -1, 1.5, True, "2", None))
def test_clients_reject_invalid_values(clients):
    with pytest.raises(ValueError, match="Clients"):
        MissionOptions(clients=clients).validate()


@pytest.mark.parametrize("clients", (1, 4))
def test_client_boundaries_are_supported(clients):
    assert MissionOptions(clients=clients).validate().clients == clients


@pytest.mark.parametrize("field,value", (
    ("map", "unknown"), ("aircraft", "nonexistent"), ("mission", "campaign"),
    ("difficulty", "impossible"), ("start", "carrier"),
    ("time_of_day", "noon"), ("weather", "storm"),
    ("loadout", "all-weapons"), ("opponent", "aliens"),
    ("seed", 1.5), ("seed", True), ("seed", "1"),
))
def test_invalid_choices_are_rejected(field, value):
    with pytest.raises(ValueError):
        replace(MissionOptions(), **{field: value}).validate()


@pytest.mark.parametrize("latitude,longitude", (
    (42.1, None), (None, 42.35), (math.nan, 42.35),
    (42.1, math.inf), (-math.inf, 42.35), (0.0, 0.0),
    (91.0, 42.35), ("42.1", 42.35),
))
def test_invalid_target_coordinates(latitude, longitude):
    with pytest.raises(ValueError):
        MissionOptions(target_lat=latitude, target_lon=longitude).validate()


def test_water_target_is_rejected():
    # Open Black Sea, well away from the coarse coastline boundary.
    assert not get_theatre("caucasus").is_land(42.0, 38.0)
    with pytest.raises(ValueError, match="water"):
        MissionOptions(target_lat=42.0, target_lon=38.0).validate()


def test_explicit_land_target_is_preserved():
    options = MissionOptions(target_lat=42.1, target_lon=42.35)
    assert options.validate() is options
    assert (options.target_lat, options.target_lon) == (42.1, 42.35)


def test_insurgents_are_limited_to_syria():
    assert MissionOptions(map="syria", opponent="insurgents").validate()
    for map_name in ("caucasus", "germany"):
        with pytest.raises(ValueError, match="Syria"):
            MissionOptions(map=map_name, opponent="insurgents").validate()


@pytest.mark.parametrize("line_units", ((), ("concrete_wall",), ("mbt", "unknown")))
def test_line_requires_known_unit_categories(line_units):
    with pytest.raises(ValueError):
        MissionOptions(mission="line", line_units=line_units).validate()


@pytest.mark.parametrize("line_units", (("aaa",), ("manpads",), ("aaa", "manpads")))
def test_disabled_air_defenses_cannot_be_the_only_line_targets(line_units):
    with pytest.raises(ValueError, match="ground-combat"):
        MissionOptions(mission="line", air_defenses=False, line_units=line_units).validate()


def test_mixed_line_selection_allows_air_defenses_to_be_disabled():
    assert MissionOptions(mission="line", air_defenses=False,
                          line_units=("infantry", "aaa")).validate()


@pytest.mark.parametrize("mission", ("facility", "line", "convoy", "sead", "cap"))
@pytest.mark.parametrize("enabled", (False, True))
def test_threat_switches_are_available_for_every_mission(mission, enabled):
    assert MissionOptions(mission=mission, enemy_cap=enabled,
                          air_defenses=enabled).validate()


@pytest.mark.parametrize("aircraft,expected", (
    ("FA_18C_hornet", {"facility", "line", "convoy", "sead", "cap"}),
    ("AH_64D_BLK_II", {"facility", "line", "convoy"}),
    ("P_51D", {"facility", "line", "convoy", "cap"}),
    ("A_10C", {"facility", "line", "convoy"}),
))
def test_representative_aircraft_capabilities(aircraft, expected):
    assert set(missions_for_aircraft(resolve_aircraft(aircraft))) == expected


@pytest.mark.parametrize("aircraft,mission", (
    ("AH_64D_BLK_II", "cap"), ("AH_64D_BLK_II", "sead"),
    ("P_51D", "sead"), ("A_10C", "cap"),
))
def test_unsupported_aircraft_mission_pair_is_rejected(aircraft, mission):
    with pytest.raises(ValueError, match="does not support"):
        MissionOptions(aircraft=aircraft, mission=mission).validate()


def test_dcs_type_id_and_python_name_resolve_to_same_aircraft():
    assert resolve_aircraft("FA-18C_hornet") is resolve_aircraft("FA_18C_hornet")


def test_catalogue_has_unique_flyable_entries_and_helicopters():
    catalogue = aircraft_catalogue()
    assert len(catalogue) > 30
    assert len({item["id"] for item in catalogue}) == len(catalogue)
    assert any(item["helicopter"] for item in catalogue)
    for item in catalogue:
        aircraft = resolve_aircraft(item["id"])
        assert aircraft.flyable
        assert item["missions"] == missions_for_aircraft(aircraft)
