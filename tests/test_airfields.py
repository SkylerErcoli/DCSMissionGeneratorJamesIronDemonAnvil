"""Every terrain base is selectable, with actual DCS parking compatibility."""
from types import SimpleNamespace

import pytest

from dcs import Mission, mapping, task
from dcs.mission import StartType

from ironanvil.airfields import airport_catalogue, resolve_airport, select_airport
from ironanvil.model import resolve_aircraft
from ironanvil.theatres import get_theatre


@pytest.mark.parametrize("key,count", (("caucasus", 21), ("syria", 224), ("germany", 227)))
def test_catalogue_includes_every_terrain_airfield_and_helipad(key, count):
    theatre = get_theatre(key)
    airports = list(theatre.terrain().airports.values())
    catalogue = airport_catalogue(key)
    assert len(catalogue) == len(airports) == count
    assert {item["id"] for item in catalogue} == {airport.id for airport in airports}
    assert {item["name"] for item in catalogue} == {airport.name for airport in airports}
    assert theatre.airports() == catalogue
    assert all(theatre.contains(item["lat"], item["lon"]) for item in catalogue)
    assert sum(item["friendly"] is True for item in catalogue) == len(theatre.blue_airports)
    assert sum(item["side"] == "red" for item in catalogue) == len(theatre.red_airports)
    assert any(item["neutral"] for item in catalogue)
    if key != "caucasus":
        assert any(item["helicopter_only"] for item in catalogue)


def test_heliport_with_a_pydcs_runway_is_still_identified_as_helicopter_only():
    item = next(item for item in airport_catalogue("syria") if item["name"] == "Qabr as Sitt")
    assert item["runways"]  # A runway entry alone does not imply fixed-wing support.
    assert item["helicopter_only"]


def _selection(key, aircraft="FA_18C_hornet", **kwargs):
    theatre = get_theatre(key)
    terrain = theatre.terrain()
    lat, lon = theatre.default_target
    target = mapping.Point.from_latlng(mapping.LatLng(lat, lon), terrain)
    return select_airport(terrain, theatre, target, resolve_aircraft(aircraft),
                          kwargs.pop("clients", 2), kwargs.pop("start", "cold"), **kwargs)


@pytest.mark.parametrize("key,name", (
    ("caucasus", "Anapa-Vityazevo"), ("caucasus", "Kutaisi"),
    ("syria", "Adana Sakirpasa"), ("syria", "Damascus"),
    ("germany", "Wittstock"), ("germany", "Stendal"),
))
def test_explicit_neutral_and_enemy_airfields_are_used_exactly(key, name):
    theatre = get_theatre(key)
    assert name not in theatre.blue_airports
    assert _selection(key, selected=name).name == name


@pytest.mark.parametrize("key", ("caucasus", "syria", "germany"))
def test_automatic_selection_still_prefers_compatible_scenario_friendly_bases(key):
    assert _selection(key).name in get_theatre(key).blue_airports


def test_airport_resolution_uses_exact_names_or_numeric_ids():
    terrain = get_theatre("syria").terrain()
    damascus = resolve_airport(terrain, "  dAmAsCuS  ")
    assert resolve_airport(terrain, damascus.id) is damascus
    assert resolve_airport(terrain, str(damascus.id)) is damascus
    for invalid in ("Dama", "nonexistent", True, None, -1, 999999):
        with pytest.raises(ValueError, match="Unknown departure airfield"):
            resolve_airport(terrain, invalid)


def test_ambiguous_names_require_explicit_ids():
    terrain = SimpleNamespace(name="test", airports={
        "first": SimpleNamespace(name="Same", id=1),
        "second": SimpleNamespace(name="SAME", id=2),
    })
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_airport(terrain, "same")
    assert resolve_airport(terrain, 2).id == 2


@pytest.mark.parametrize("start", ("cold", "hot", "runway", "air"))
def test_fixed_wing_rejects_helicopter_only_home_without_silent_fallback(start):
    with pytest.raises(ValueError, match="helicopter-only"):
        _selection("syria", selected="Naqoura", start=start)
    with pytest.raises(ValueError, match="helicopter-only"):
        _selection("syria", selected="Qabr as Sitt", start=start)


@pytest.mark.parametrize("start", ("cold", "hot"))
def test_selected_heliport_checks_parking_for_the_entire_flight(start):
    assert _selection("germany", aircraft="UH_1H", selected="H FRG 01",
                      clients=2, start=start).name == "H FRG 01"
    with pytest.raises(ValueError, match="2 compatible parking spaces.*3 are needed"):
        _selection("germany", aircraft="UH_1H", selected="H FRG 01", clients=3, start=start)


@pytest.mark.parametrize("start", ("runway", "air"))
def test_runway_and_air_starts_do_not_require_parking(start):
    assert _selection("germany", aircraft="UH_1H", selected="H FRG 01",
                      clients=4, start=start).name == "H FRG 01"


@pytest.mark.parametrize("key,name,aircraft,clients", (
    ("caucasus", "Anapa-Vityazevo", "FA_18C_hornet", 4),
    ("syria", "Damascus", "FA_18C_hornet", 4),
    ("germany", "Wittstock", "FA_18C_hornet", 4),
    ("syria", "Naqoura", "UH_1H", 2),
    ("germany", "H FRG 01", "UH_1H", 2),
))
def test_selected_airfields_really_spawn_all_clients_with_unique_compatible_parking(
        key, name, aircraft, clients):
    airport = _selection(key, aircraft=aircraft, selected=name, clients=clients)
    mission = Mission(airport.position._terrain)
    airport.set_blue()
    flight = mission.flight_group_from_airport(
        mission.country("USA"), "CLIENTS", resolve_aircraft(aircraft), airport,
        maintask=task.CAS, group_size=clients, start_type=StartType.Cold,
    )
    assert len(flight.units) == clients
    assert flight.points[0].airdrome_id == airport.id
    assert len({unit.parking for unit in flight.units}) == clients
    assert all(unit.parking is not None for unit in flight.units)


def test_automatic_selection_can_use_another_airfield_if_preferred_bases_are_unsuitable():
    original = get_theatre("caucasus")
    terrain = original.terrain()
    lat, lon = original.default_target
    target = mapping.Point.from_latlng(mapping.LatLng(lat, lon), terrain)
    theatre = SimpleNamespace(blue_airports=("Nonexistent",), label=original.label)
    airport = select_airport(terrain, theatre, target, resolve_aircraft("FA_18C_hornet"),
                             4, "cold")
    assert airport.name in terrain.airports
    assert len(airport.free_parking_slots(resolve_aircraft("FA_18C_hornet"))) >= 4
