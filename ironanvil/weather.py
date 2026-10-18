"""Repeatable DCS weather presets, including actual rain, fog and winds.

Cloud names and permitted bases come from the pinned pydcs cloud catalogue.
Rain and thunderstorms deliberately use DCS's legacy cloud parameters: pydcs
serializes ``iprecptns`` as zero whenever a modern cloud preset is selected.
All speeds are metres per second, distances/heights are metres, and QNH is mmHg.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

from dcs.cloud_presets import Clouds
from dcs.weather import Weather, Wind


@dataclass(frozen=True)
class WeatherPreset:
    label: str
    cloud_preset: Clouds | None = None
    cloud_base: int = 2500
    cloud_density: int = 0
    cloud_thickness: int = 200
    precipitation: Weather.Preceptions = Weather.Preceptions.None_
    wind_speeds: tuple[int, int, int] = (2, 4, 8)
    turbulence: int = 0
    visibility: int = 80000
    temperature: int = 20
    qnh: int = 760
    fog_visibility: int = 25000
    fog_thickness: int = 0


WEATHERS: dict[str, WeatherPreset | None] = {
    "clear": WeatherPreset("Clear skies"),
    "scattered": WeatherPreset(
        "Scattered clouds", Clouds.LightScattered1, cloud_base=2400,
        wind_speeds=(3, 6, 11),
    ),
    "broken": WeatherPreset(
        "Broken clouds", Clouds.Broken1, cloud_base=2400,
        wind_speeds=(4, 8, 14), temperature=19,
    ),
    "overcast": WeatherPreset(
        "Overcast", Clouds.Overcast1, cloud_base=1800,
        wind_speeds=(5, 10, 16), temperature=18, qnh=755,
    ),
    "rain": WeatherPreset(
        "Rain", cloud_base=1200, cloud_density=9, cloud_thickness=1800,
        precipitation=Weather.Preceptions.Rain, wind_speeds=(5, 10, 16),
        turbulence=5, visibility=25000, temperature=18, qnh=752,
    ),
    "storm": WeatherPreset(
        "Thunderstorm", cloud_base=1000, cloud_density=10, cloud_thickness=2200,
        precipitation=Weather.Preceptions.Thunderstorm, wind_speeds=(8, 14, 20),
        turbulence=18, visibility=15000, temperature=18, qnh=745,
    ),
    "fog": WeatherPreset(
        "Fog / low visibility", wind_speeds=(1, 3, 6), visibility=50000,
        temperature=16, fog_visibility=3000, fog_thickness=150,
    ),
    "windy": WeatherPreset(
        "Strong winds", Clouds.Scattered1, cloud_base=3000,
        wind_speeds=(10, 17, 25), turbulence=15,
    ),
    "random": None,
}
# Retain saved settings and command lines from earlier releases.
WEATHERS["cloudy"] = WEATHERS["broken"]
WEATHER_LABELS = {
    key: preset.label if preset is not None else "Random (flyable conditions)"
    for key, preset in WEATHERS.items()
}
WEATHER_LABELS["cloudy"] = "Cloudy (legacy)"

# Explicitly selected fog and storms are useful challenges; random conditions
# avoid them and favour the less demanding presets.
_RANDOM_CHOICES = (
    "clear", "clear", "scattered", "scattered", "broken", "broken",
    "overcast", "rain", "windy",
)


def apply_weather(mission, preset: str, rng: random.Random) -> str:
    """Replace mission weather and return its resolved, canonical preset key.

    ``random`` uses only the supplied RNG. Resetting the complete weather object
    prevents fog, precipitation or dynamic weather leaking from a previous
    selection if the same mission object is reused.
    """
    if preset not in WEATHERS:
        raise ValueError(f"Unknown weather preset: {preset!r}")
    resolved = rng.choice(_RANDOM_CHOICES) if preset == "random" else preset
    if resolved == "cloudy":
        resolved = "broken"
    settings = WEATHERS[resolved]
    assert settings is not None

    weather = Weather(mission.terrain)
    weather.name = settings.label
    weather.clouds_preset = settings.cloud_preset.value if settings.cloud_preset else None
    weather.clouds_base = settings.cloud_base
    weather.clouds_density = settings.cloud_density
    weather.clouds_thickness = settings.cloud_thickness
    weather.clouds_iprecptns = settings.precipitation
    weather.season_temperature = settings.temperature
    weather.qnh = settings.qnh
    weather.visibility_distance = settings.visibility
    weather.turbulence_at_ground = settings.turbulence
    weather.enable_fog = settings.fog_thickness > 0
    weather.fog_thickness = settings.fog_thickness
    weather.fog_visibility = settings.fog_visibility

    direction = rng.randrange(360)
    weather.wind_at_ground = Wind(direction, settings.wind_speeds[0])
    weather.wind_at_2000 = Wind((direction + 15) % 360, settings.wind_speeds[1])
    weather.wind_at_8000 = Wind((direction + 30) % 360, settings.wind_speeds[2])
    mission.weather = weather
    return resolved
