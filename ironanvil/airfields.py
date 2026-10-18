"""The complete terrain airport catalogue and explicit departure selection.

The scenario's default friendly/enemy lists describe ownership, not availability.
Any airfield in the pinned DCS terrain data can be selected as the home base;
the mission builder makes that selected base friendly before creating the flight.
"""
from __future__ import annotations

from functools import lru_cache


def _helicopter_only(airport):
    """Include helicopter airfields which pydcs also describes with a runway."""
    return not airport.runways or bool(airport.parking_slots) and not any(
        slot.airplanes for slot in airport.parking_slots
    )


@lru_cache(maxsize=3)
def airport_catalogue(map_key):
    """Return every named airfield/helipad supplied by the selected terrain.

    ``parking`` is the total parking count, not a promise that a particular
    aircraft fits.  Ground-start compatibility is checked against the actual
    selected aircraft by :func:`select_airport`.
    """
    from .theatres import get_theatre

    theatre = get_theatre(map_key)
    result = []
    for airport in theatre.terrain().airports.values():
        position = airport.position.latlng()
        side = ("blue" if airport.name in theatre.blue_airports else
                "red" if airport.name in theatre.red_airports else "neutral")
        helicopter_only = _helicopter_only(airport)
        result.append({
            "id": airport.id, "name": airport.name,
            "lat": position.lat, "lon": position.lng,
            "runways": bool(airport.runways), "parking": len(airport.parking_slots),
            "helicopter": helicopter_only, "helicopter_only": helicopter_only,
            "friendly": True if side == "blue" else False if side == "red" else None,
            "neutral": side == "neutral", "side": side,
        })
    return sorted(result, key=lambda item: (item["name"].casefold(), item["id"]))


def resolve_airport(terrain, name_or_id):
    """Resolve an exact name (case-insensitive) or numeric DCS airport ID.

    Do not use partial matching: a near match could silently send a flight to a
    different base.  Numeric strings from command-line options are accepted.
    """
    if isinstance(name_or_id, bool) or name_or_id is None:
        matches = []
    else:
        name = str(name_or_id).strip().casefold()
        matches = [airport for airport in terrain.airports.values()
                   if airport.name.casefold() == name]
        if not matches and name.isdecimal():
            matches = [airport for airport in terrain.airports.values()
                       if airport.id == int(name)]
    if not matches:
        raise ValueError(f"Unknown departure airfield {name_or_id!r} on {terrain.name}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous departure airfield {name_or_id!r}; use its numeric airport ID")
    return matches[0]


def _compatibility_error(airport, aircraft, clients, start):
    if not aircraft.helicopter and _helicopter_only(airport):
        return (f"{airport.name} is a helicopter-only airfield; choose another airfield "
                f"for {aircraft.id}, or choose a helicopter")
    if start in ("cold", "hot"):
        available = len(airport.free_parking_slots(aircraft))
        if available < clients:
            return (f"{airport.name} has {available} compatible parking spaces for {aircraft.id}; "
                    f"{clients} are needed. Choose another airfield, fewer pilots, "
                    "or a runway/air start")
    return None


def select_airport(terrain, theatre, target, aircraft, clients, start, selected=None):
    """Choose the requested home exactly, or the nearest suitable default base.

    Explicit selections can be neutral or scenario enemy bases. They never
    silently fall back to another airport. Automatic selection keeps the
    existing friendly-base preference, using other suitable terrain airfields
    only when none of the preferred bases can host the requested flight.

    Runway and air starts do not require parking. A fixed-wing flight still
    needs a fixed-wing home base because its route returns there to land.
    """
    if selected is not None and str(selected).strip():
        airport = resolve_airport(terrain, selected)
        error = _compatibility_error(airport, aircraft, clients, start)
        if error:
            raise ValueError(error)
        return airport

    compatible = [airport for airport in terrain.airports.values()
                  if not _compatibility_error(airport, aircraft, clients, start)]
    preferred = [airport for airport in compatible if airport.name in theatre.blue_airports]
    candidates = preferred or compatible
    if not candidates:
        raise ValueError(f"No {theatre.label} airfield can host {clients} {aircraft.id} "
                         f"pilots with a {start} start; choose fewer pilots or another start type")
    return min(candidates, key=lambda airport: airport.position.distance_to_point(target))
