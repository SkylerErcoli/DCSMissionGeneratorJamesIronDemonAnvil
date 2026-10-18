"""Verify the weather DCS receives in the generated mission archive."""
import random
import zipfile

import pytest

from dcs import Mission, lua
from dcs.weather import Cyclone
from ironanvil.weather import WEATHER_LABELS, WEATHERS, apply_weather


@pytest.mark.parametrize("preset", WEATHERS)
def test_every_weather_survives_miz_serialization_and_reload(tmp_path, preset):
    mission = Mission()
    resolved = apply_weather(mission, preset, random.Random(5))
    assert resolved in WEATHERS
    assert resolved not in ("random", "cloudy")
    path = tmp_path / f"{preset}.miz"
    mission.save(str(path))
    with zipfile.ZipFile(path) as archive:
        saved = lua.loads(archive.read("mission").decode())["mission"]["weather"]
    assert saved == mission.weather.dict()
    reloaded = Mission()
    reloaded.load_file(str(path))
    assert reloaded.weather.dict() == saved
    assert reloaded.weather.name == WEATHER_LABELS[resolved]


def test_clouds_use_dcs_catalogue_and_distinct_cloud_cover():
    mission = Mission()
    for key, preset in (("scattered", "Preset1"), ("broken", "Preset13"),
                        ("overcast", "Preset21")):
        apply_weather(mission, key, random.Random(7))
        clouds = mission.weather.dict()["clouds"]
        assert clouds["preset"] == preset
        assert clouds["base"] >= 1800
    apply_weather(mission, "clear", random.Random(7))
    assert "preset" not in mission.weather.dict()["clouds"]
    assert mission.weather.dict()["clouds"]["density"] == 0


@pytest.mark.parametrize("key, precipitation, density", [("rain", 1, 9), ("storm", 2, 10)])
def test_precipitation_is_serialized_with_compatible_clouds(tmp_path, key, precipitation, density):
    mission = Mission()
    apply_weather(mission, key, random.Random(11))
    path = tmp_path / "rain.miz"
    mission.save(str(path))
    with zipfile.ZipFile(path) as archive:
        weather = lua.loads(archive.read("mission").decode())["mission"]["weather"]
    assert weather["clouds"]["iprecptns"] == precipitation
    assert weather["clouds"]["density"] == density
    assert "preset" not in weather["clouds"]
    assert weather["clouds"]["thickness"] >= 1800
    assert weather["visibility"]["distance"] < 80000


def test_fog_and_wind_change_real_dcs_weather_fields(tmp_path):
    mission = Mission()
    apply_weather(mission, "fog", random.Random(12))
    fog = mission.weather.dict()
    assert fog["enable_fog"] is True
    assert fog["fog"] == {"visibility": 3000, "thickness": 150}
    apply_weather(mission, "clear", random.Random(12))
    clear = mission.weather.dict()
    apply_weather(mission, "windy", random.Random(12))
    path = tmp_path / "wind.miz"
    mission.save(str(path))
    with zipfile.ZipFile(path) as archive:
        windy = lua.loads(archive.read("mission").decode())["mission"]["weather"]
    for level in ("atGround", "at2000", "at8000"):
        assert windy["wind"][level]["speed"] > clear["wind"][level]["speed"]
        assert 0 <= windy["wind"][level]["dir"] < 360
    assert windy["groundTurbulence"] > clear["groundTurbulence"]


def test_reusing_mission_clears_previous_weather_state():
    mission = Mission()
    apply_weather(mission, "storm", random.Random(1))
    mission.weather.enable_fog = True
    mission.weather.fog_thickness = 500
    mission.weather.enable_dust = True
    mission.weather.dust_density = 1000
    mission.weather.atmosphere_type = 1
    mission.weather.cyclones.append(Cyclone())
    apply_weather(mission, "clear", random.Random(9))
    fresh = Mission()
    apply_weather(fresh, "clear", random.Random(9))
    assert mission.weather.dict() == fresh.weather.dict()
    assert mission.weather.enable_fog is False
    assert mission.weather.clouds_iprecptns.value == 0
    assert mission.weather.atmosphere_type == 0
    assert mission.weather.cyclones == []


def test_legacy_cloudy_alias_preserves_saved_settings():
    first, second = Mission(), Mission()
    assert apply_weather(first, "cloudy", random.Random(18)) == "broken"
    apply_weather(second, "broken", random.Random(18))
    assert first.weather.dict() == second.weather.dict()


def test_random_weather_is_repeatable_varied_and_uses_only_supplied_rng():
    before = random.getstate()
    results = set()
    for seed in range(50):
        first, second = Mission(), Mission()
        one = apply_weather(first, "random", random.Random(seed))
        two = apply_weather(second, "random", random.Random(seed))
        assert one == two
        assert first.weather.dict() == second.weather.dict()
        results.add(one)
    assert results == {"clear", "scattered", "broken", "overcast", "rain", "windy"}
    assert random.getstate() == before


def test_unknown_weather_does_not_mutate_the_mission():
    mission = Mission()
    original = mission.weather.dict()
    with pytest.raises(ValueError, match="Unknown weather preset"):
        apply_weather(mission, "tornado", random.Random(1))
    assert mission.weather.dict() == original
