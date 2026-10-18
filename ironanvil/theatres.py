"""DCS terrain identities and scenario sides, independent of GUI projections."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theatre:
    key: str
    label: str
    bounds: tuple[float, float, float, float]  # west, south, east, north
    default_target: tuple[float, float]  # latitude, longitude
    blue_airports: tuple[str, ...]
    red_airports: tuple[str, ...]

    def terrain(self):
        from dcs import terrain
        return getattr(terrain, {"caucasus": "Caucasus", "syria": "Syria", "germany": "Germany"}[self.key])()

    def airports(self):
        from .airfields import airport_catalogue
        return airport_catalogue(self.key)

    def contains(self, lat, lon):
        west, south, east, north = self.bounds
        return south <= lat <= north and west <= lon <= east

    def is_land(self, lat, lon):
        from .mapdata import is_land
        return self.contains(lat, lon) and is_land(lat, lon)


THEATRES = {
    "caucasus": Theatre("caucasus", "Caucasus", (36.0, 40.0, 46.0, 46.0), (42.1, 42.35),
                        ("Batumi", "Kobuleti"), ("Kutaisi", "Senaki-Kolkhi", "Gudauta")),
    "syria": Theatre("syria", "Syria", (32.0, 31.0, 42.0, 38.2), (35.2, 37.0),
                     ("Incirlik", "Ramat David", "Akrotiri"), ("Abu al-Duhur", "Damascus", "Al Qusayr")),
    "germany": Theatre("germany", "Cold War Germany", (6.3, 49.0, 17.0, 56.0), (52.55, 11.4),
                       ("Fassberg", "Wunstorf", "Buckeburg"), ("Stendal", "Gardelegen", "Sperenberg")),
}


def get_theatre(name):
    try:
        return THEATRES[name.lower()]
    except (AttributeError, KeyError):
        raise ValueError(f"Unknown map {name!r}; choose {', '.join(THEATRES)}") from None
