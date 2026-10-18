"""The selected airfield must survive full mission generation, not just lookup."""
import json
from zipfile import ZipFile

import pytest
from dcs import Mission, lua

from ironanvil.generator import generate, PLAYER_GROUP
from ironanvil.model import MissionOptions


@pytest.mark.parametrize("map_name,name", (
    ("caucasus", "Anapa-Vityazevo"), ("syria", "Damascus"), ("germany", "Stendal"),
))
def test_selected_nondefault_base_is_friendly_and_supplied(map_name, name, tmp_path):
    path = generate(MissionOptions(map=map_name, departure_airport=name,
                                  enemy_cap=False, air_defenses=False), tmp_path / "selected.miz")
    with ZipFile(path) as archive:
        metadata = json.loads(archive.read("ironanvil.json"))
        warehouses = lua.loads(archive.read("warehouses").decode())["warehouses"]
    assert metadata["home_airport"] == name
    assert warehouses["airports"][metadata["home_airport_id"]]["coalition"] == "BLUE"
    assert warehouses["airports"][metadata["home_airport_id"]]["unlimitedFuel"]
    assert warehouses["airports"][metadata["home_airport_id"]]["unlimitedMunitions"]


@pytest.mark.parametrize("map_name,name", (("syria", "At Tanf"), ("germany", "H FRG 01")))
@pytest.mark.parametrize("start", ("cold", "hot", "runway", "air"))
def test_helicopter_home_without_a_runway_has_a_valid_return_route(map_name, name, start, tmp_path):
    path = generate(MissionOptions(map=map_name, departure_airport=name, start=start,
                                  aircraft="AH_64D_BLK_II", enemy_cap=False, air_defenses=False),
                    tmp_path / "helipad.miz")
    reloaded = Mission()
    reloaded.load_file(str(path))
    flight = reloaded.coalition["blue"].find_group(PLAYER_GROUP)
    assert len(flight.units) == 2
    home = reloaded.terrain.airports[name]
    assert home.is_blue()
    assert flight.points[-1].airdrome_id == home.id
    assert flight.points[-1].action.value == "Landing"
