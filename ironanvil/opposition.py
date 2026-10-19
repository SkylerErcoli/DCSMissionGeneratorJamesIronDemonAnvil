"""Stock DCS enemy factions and automatic sizing for rotary-wing sorties."""
from __future__ import annotations

FACTION_LABELS = {
    "regular": "Russian regulars",
    "syrian": "Syrian army",
    "western": "Western task force",
    "insurgents": "Insurgent militia",
}

# Translate roles, retaining objective names, unit IDs, positions and routes.
# Every SAM choice is self-contained: no incomplete Hawk/Patriot batteries.
ROLE_TYPES = {
    "tank": ("T-72B",), "ifv": ("BMP-2",), "apc": ("BTR-80", "BTR-60"),
    "atgm": ("BRDM-2_malyutka",), "infantry": ("Infantry AK", "Infantry AK Ins"),
    "truck": ("Ural-375",), "fuel": ("Ural ATsP-6",),
    "command": ("Ural-375 PBU", "ZIL-131 KUNG"), "artillery": ("SAU Msta",),
    "aaa": ("ZSU-23-4 Shilka", "Ural-375 ZU-23", "Ural-375 ZU-23 Insurgent"),
    "manpads": ("SA-18 Igla manpad", "Igla manpad INS"),
    "sam": ("Osa 9A33 ln", "Kub 1S91 str", "Kub 2P25 ln"),
    "radar": ("1L13 EWR",),
}
_ROLE = {kind: role for role, kinds in ROLE_TYPES.items() for kind in kinds}
EQUIPMENT = {
    "syrian": {
        "tank": ("T-55", "T-72B"), "ifv": ("BMP-1", "BMP-2"),
        "apc": ("BTR-60", "BRDM-2"), "artillery": ("SAU Gvozdika",),
    },
    "western": {
        "tank": ("M-1 Abrams",), "ifv": ("M-2 Bradley",), "apc": ("M-113",),
        "atgm": ("M1045 HMMWV TOW",), "infantry": ("Soldier M4", "Soldier M249"),
        "truck": ("M 818",), "fuel": ("M978 HEMTT Tanker",),
        "command": ("M1043 HMMWV Armament",), "artillery": ("M-109",),
        "aaa": ("Vulcan",), "manpads": ("Soldier stinger",),
        "sam": ("Roland ADS", "M48 Chaparral"),
        "radar": ("FPS-117",),
    },
    "insurgents": {
        "tank": ("T-55",), "ifv": ("BMP-1",), "apc": ("BTR-60", "BRDM-2"),
        "atgm": ("BRDM-2_malyutka",), "infantry": ("Infantry AK Ins",),
        "command": ("tt_KORD",), "artillery": ("SAU Gvozdika",),
        "aaa": ("tt_ZU-23", "Ural-375 ZU-23 Insurgent"),
        "manpads": ("Igla manpad INS",), "sam": ("tt_ZU-23",),
    },
}


def enemy_country(mission, faction, *, air=False):
    from dcs import countries
    country_type = {
        "regular": countries.Russia, "syrian": countries.Syria,
        "western": countries.CombinedJointTaskForcesRed,
        # Militia can receive supporting Syrian fighters when CAP is enabled.
        "insurgents": countries.Syria if air else countries.Insurgents,
    }[faction]
    coalition = mission.coalition["red"]
    return coalition.country(country_type.name) or coalition.add_country(country_type())


def fighter_type(options):
    from dcs import planes
    return {
        "regular": planes.MiG_21Bis if options.map == "germany" else planes.MiG_29A,
        "syrian": planes.MiG_23MLD, "western": planes.F_16A,
        "insurgents": planes.MiG_21Bis,
    }[options.opponent]


def apply_faction(country, faction, rng):
    """Convert generated ground roles once, without changing runtime references."""
    from dcs import vehicles
    profile = EQUIPMENT.get(faction, {})
    if profile:
        for group in country.vehicle_group + country.static_group:
            for unit in group.units:
                choices = profile.get(_ROLE.get(unit.type))
                if choices:
                    unit.type = vehicles.vehicle_map[rng.choice(choices)].id
    return sorted({unit.type for group in country.vehicle_group for unit in group.units})


def helicopter_sortie(options):
    from .model import resolve_aircraft
    return bool(resolve_aircraft(options.aircraft).helicopter)


def ground_level(options):
    level = ("easy", "normal", "hard", "extreme").index(options.difficulty) + 1
    return max(1, level - 1) if helicopter_sortie(options) else level


def site_scale(options):
    return .65 if helicopter_sortie(options) else 1
