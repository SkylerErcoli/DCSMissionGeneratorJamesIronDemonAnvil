"""Validated inputs shared by the CLI, desktop planner, and mission builder."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import math
import os

MISSION_LABELS = {"facility": "Strike — facility", "line": "Strike — fortified line",
                  "convoy": "Strike — moving convoy", "sead": "SEAD / DEAD", "cap": "CAP"}
LINE_UNITS = ("mbt", "ifv", "apc", "atgm", "infantry", "manpads", "aaa", "artillery")


def default_output_dir():
    # No writes to a guessed DCS installation. A standard Saved Games path is safe
    # on Windows and a normal documents-style output directory on other systems.
    if os.name == "nt":
        base = Path.home() / "Saved Games"
        dcs = base / "DCS"
        if not dcs.exists() and (base / "DCS.openbeta").exists():
            dcs = base / "DCS.openbeta"
        return dcs / "Missions" / "IronAnvil"
    return Path.home() / "IronAnvil" / "Missions"


@lru_cache(maxsize=1)
def aircraft_types():
    from dcs.planes import plane_map
    from dcs.helicopters import helicopter_map
    return {c.__name__: c for c in [*plane_map.values(), *helicopter_map.values()]
            if getattr(c, "flyable", False)}


def resolve_aircraft(name):
    types = aircraft_types()
    if name in types:
        return types[name]
    for cls in types.values():
        if cls.id == name:
            return cls
    raise ValueError(f"Unknown flyable aircraft {name!r}; run python -m ironanvil list")


def missions_for_aircraft(cls):
    tasks = {task.__name__ for task in cls.tasks}
    result = []
    if tasks & {"CAS", "GroundAttack", "PinpointStrike"}:
        result.extend(("facility", "line", "convoy"))
    if "SEAD" in tasks:
        result.append("sead")
    if tasks & {"CAP", "FighterSweep", "Intercept"}:
        result.append("cap")
    return result


@lru_cache(maxsize=1)
def aircraft_catalogue():
    return sorted([{"id": cls.__name__, "name": cls.id,
                    "helicopter": bool(getattr(cls, "helicopter", False)),
                    "missions": missions_for_aircraft(cls)} for cls in aircraft_types().values()
                   if missions_for_aircraft(cls)],
                  key=lambda a: a["name"].lower())


@dataclass(frozen=True)
class MissionOptions:
    map: str = "caucasus"
    aircraft: str = "FA_18C_hornet"
    mission: str = "facility"
    clients: int = 2
    difficulty: str = "normal"
    enemy_cap: bool = True
    air_defenses: bool = True
    target_lat: float | None = None
    target_lon: float | None = None
    seed: int = 1
    start: str = "cold"
    time_of_day: str = "day"
    weather: str = "clear"
    tanker: bool = False
    awacs: bool = False
    loadout: str = "auto"
    line_units: tuple[str, ...] = ("mbt", "ifv", "infantry", "aaa")
    base_detail: bool = True
    output_dir: str | None = None
    opponent: str = "regular"

    def validate(self):
        from .theatres import get_theatre
        theatre = get_theatre(self.map)
        if not isinstance(self.clients, int) or isinstance(self.clients, bool) or not 1 <= self.clients <= 4:
            raise ValueError("Clients must be an integer from 1 to 4")
        choices = {
            "mission": MISSION_LABELS, "difficulty": ("easy", "normal", "hard", "extreme"),
            "start": ("cold", "hot", "runway", "air"),
            "time_of_day": ("day", "dawn", "dusk", "night", "random"),
            "weather": ("clear", "cloudy"), "loadout": ("auto", "default"),
            "opponent": ("regular", "insurgents"),
        }
        for field, allowed in choices.items():
            if getattr(self, field) not in allowed:
                raise ValueError(f"Invalid {field}: {getattr(self, field)!r}")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("Seed must be an integer")
        aircraft = resolve_aircraft(self.aircraft)
        if self.mission not in missions_for_aircraft(aircraft):
            raise ValueError(f"{aircraft.id} does not support {self.mission} missions")
        if self.opponent == "insurgents" and self.map != "syria":
            raise ValueError("The insurgent opponent is available on Syria only")
        if any(unit not in LINE_UNITS for unit in self.line_units):
            raise ValueError("Unknown fortified-line unit category")
        if self.mission == "line" and not self.line_units:
            raise ValueError("Select at least one fortified-line unit category")
        if (self.target_lat is None) != (self.target_lon is None):
            raise ValueError("Supply both target latitude and longitude")
        if self.target_lat is not None:
            try:
                finite = math.isfinite(self.target_lat) and math.isfinite(self.target_lon)
            except TypeError:
                finite = False
            if not finite or not theatre.contains(self.target_lat, self.target_lon):
                raise ValueError("Target coordinates must be finite and inside the selected map")
            if not theatre.is_land(self.target_lat, self.target_lon):
                raise ValueError("The target is in water according to the coastline mask; select a point inland")
        if self.mission == "line" and not self.air_defenses and not set(self.line_units) - {"aaa", "manpads"}:
            raise ValueError("Air defenses are disabled; select at least one ground-combat unit for the line")
        return self
