"""Occupied, varied facility complexes built from DCS's actual object catalogue.

The coastline check only rejects obvious water. DCS terrain elevation, slope and
the exact footprints of most scenery meshes still require a Mission Editor check.
The container perimeter uses the nominal 40-foot length; HESCO pieces are partial
protective screens, never a claim of a calibrated, completely sealed perimeter.
"""
from __future__ import annotations

import math
import random

from dcs import statics, vehicles
from dcs.unit import Skill

from .mapdata import is_land


FACILITY_LABELS = {
    "random": "Random facility",
    "fuel": "Fuel depot",
    "command": "Command post",
    "ammunition": "Ammunition depot",
    "factory": "Factory / repair works",
    "radar": "Radar station",
}
_STYLES = {
    "fuel": "fuel and service compound",
    "command": "command and communications outpost",
    "ammunition": "container ammunition yard",
    "factory": "workshop and repair yard",
    "radar": "radar and communications station",
}
_CONTAINER_LENGTH = 12.192


def _on_land(point):
    coordinates = point.latlng()
    return is_land(coordinates.lat, coordinates.lng)


def _offset(point, dx, dz):
    return point.new_in_same_map(point.x + dx, point.y + dz)


def _land_offset(point, dx, dz):
    """Keep every placed object on land, compacting coastal layouts if needed."""
    for scale in (1, .85, .65, .45, .25, 0):
        candidate = _offset(point, dx * scale, dz * scale)
        if _on_land(candidate):
            return candidate
    raise ValueError("Facility target is in water; select a point farther inland")


def _has_room(point,*,screen_woodland=True):
    from .geography import suitable_ground
    from .theatres import THEATRES
    theatre=THEATRES[type(point._terrain).__name__.lower()]
    return (_on_land(point) and all(_on_land(point.point_from_heading(bearing,170)) for bearing in range(0,360,45))
            and suitable_ground(point,theatre,footprint=170,screen_woodland=screen_woodland))


def _site_positions(point, count, rng):
    from .geography import woodland_clear
    from .theatres import THEATRES
    theatre=THEATRES[type(point._terrain).__name__.lower()]
    # An unsafe, explicitly forced primary keeps its historical override.
    # Automatically planned primaries already have a larger clear footprint.
    screen_woodland=woodland_clear(point,theatre,footprint=170)
    if not _on_land(point):
        raise ValueError("Facility target is in water; select a point farther inland")
    positions = [point]
    notes = []
    initial_heading = rng.randrange(360)
    for index in range(1, count):
        preferred = initial_heading + (index - 1) * 120
        selected = None
        # Prefer a complete footprint and distinct sites. Near a coast, rotate
        # inland before increasing the distance or compacting the decoration.
        for require_room, distances in ((True, (440, 520, 620)),
                                        (True, (760, 900)),
                                        (False, (440, 520, 620, 760, 900))):
            for distance in distances:
                for turn in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                    candidate = point.point_from_heading(preferred + turn, distance)
                    if any(candidate.distance_to_point(existing) < 300 for existing in positions):
                        continue
                    if (_has_room(candidate,screen_woodland=screen_woodland) if require_room else
                            _on_land(candidate) and (not screen_woodland or woodland_clear(candidate,theatre,footprint=170))):
                        selected = candidate
                        if distance > 650 or not require_room:
                            notes.append(f"Site {index + 1} moved inland or compacted to avoid coastal water or woodland.")
                        break
                if selected is not None:
                    break
            if selected is not None:
                break
        if selected is None:
            notes.append(
                f"Coastline allowed only {len(positions)} separated sites; "
                "choose a point farther inland for the full complex."
            )
            break
        positions.append(selected)
    return positions, notes


class _Site:
    def __init__(self, mission, country, point, index, kind, heading, rng, level):
        self.mission, self.country, self.point = mission, country, point
        self.index, self.kind, self.heading = index, kind, heading
        self.rng, self.level = rng, level
        self.objectives = []
        self.decorations = []
        self.groups = []
        self.garrison_units = 0
        self.perimeter = None

    def local(self, x, z, jitter=0):
        if jitter:
            x += self.rng.uniform(-jitter, jitter)
            z += self.rng.uniform(-jitter, jitter)
        radians = math.radians(self.heading)
        return _land_offset(self.point, x * math.cos(radians) - z * math.sin(radians),
                            x * math.sin(radians) + z * math.cos(radians))

    def static(self, title, kind, x, z, *, objective=False, angle=0, jitter=0):
        prefix = "OBJECTIVE" if objective else "FACILITY"
        name = f"{prefix} SITE {self.index} {title}"
        group = self.mission.static_group(
            self.country, name, kind, self.local(x, z, jitter),
            heading=(self.heading + angle) % 360,
        )
        unit_name = group.units[0].name
        (self.objectives if objective else self.decorations).append(unit_name)
        return unit_name

    def group(self, title, types, positions):
        name = f"FACILITY SITE {self.index} {title}"
        point = self.local(*positions[0])
        group = self.mission.vehicle_group_platoon(
            self.country, name, [vehicles.vehicle_map[kind] for kind in types],
            point, heading=self.heading,
        )
        group.set_skill((Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[self.level - 1])
        for unit, position in zip(group.units, positions):
            unit.position = self.local(*position)
            unit.heading = (self.heading + self.rng.uniform(-8, 8)) % 360
        self.groups.append(group.name)
        return group

    def occupy(self):
        truck = "Ural ATsP-6" if self.kind == "fuel" else "Ural-375"
        self.group("parked logistics", [truck, "Ural-375"], [(-38, -62), (0, -62)])
        count = 2 + self.level
        positions = [(65, -60), (71, -56), (65, -49), (-75, 45), (-70, -45), (80, 25)][:count]
        self.group("garrison", ["Infantry AK"] * count, positions)
        self.garrison_units = count
        if self.level >= 3 and self.kind == "command":
            self.group("guard vehicle", ["BMP-2"], [(82, -25)])
            self.garrison_units += 1

    def metadata(self):
        location = self.point.latlng()
        return {
            "name": f"Site {self.index}: {FACILITY_LABELS[self.kind]}",
            "type": self.kind, "style": _STYLES[self.kind],
            "x": self.point.x, "z": self.point.y,
            "latitude": location.lat, "longitude": location.lng,
            "heading": self.heading,
            "objective_statics": list(self.objectives),
            "objective_count": len(self.objectives),
            "decoration_statics": list(self.decorations),
            "decoration_count": len(self.decorations),
            "vehicle_groups": list(self.groups),
            "garrison_units": self.garrison_units,
            "perimeter": self.perimeter,
        }


def _container_perimeter(site):
    across, deep = 18, 14
    width, depth = across * _CONTAINER_LENGTH, deep * _CONTAINER_LENGTH
    for side in (-1, 1):
        for index in range(across):
            if side == -1 and index in (across // 2 - 1, across // 2):
                continue  # A two-container-width vehicle entrance.
            site.static(f"container boundary horizontal {side} {index}",
                        statics.Fortification.Container_40ft,
                        -width / 2 + (index + .5) * _CONTAINER_LENGTH, side * depth / 2)
        for index in range(deep):
            site.static(f"container boundary vertical {side} {index}",
                        statics.Fortification.Container_40ft,
                        side * width / 2, -depth / 2 + (index + .5) * _CONTAINER_LENGTH,
                        angle=90)
    site.static("gate office", statics.Fortification.Container_office, 32, -depth / 2 - 14)
    site.static("open entrance barrier", statics.Fortification.BoomBarrier_open, 6, -depth / 2)
    site.perimeter = {
        "kind": "40ft container boundary", "nominal_length": _CONTAINER_LENGTH,
        "width": width, "depth": depth, "gate_width": 2 * _CONTAINER_LENGTH,
        "note": "Nominal container dimensions; verify DCS mesh alignment and terrain.",
    }


def _protective_screens(site):
    layout=site.rng.choice(('HESCO','concrete blast screens','mixed screens'))
    for index, (x, z, angle) in enumerate(((-94, 60, 0), (94, 60, 0),
                                         (-94, -38, 90), (94, -38, 90)), 1):
        kind=(statics.Fortification.Twall_x6_3mts if layout=='concrete blast screens' or
              layout=='mixed screens' and index%2 else statics.Fortification.HESCO_wallperimeter_1)
        site.static(f"protective screen {index}", kind,
                    x, z, angle=angle)
    if site.rng.random()<.65:
        site.static('watchtower',statics.Fortification.HESCO_watchtower_1,90,85,angle=180)
    site.perimeter = {"kind": 'partial '+layout, "closed": False,
                      "note": "Mesh lengths are not calibrated; these are separated screens."}


def _fuel(site):
    for index, (kind, x) in enumerate(((statics.Warehouse.Tank, -48),
                                      (statics.Warehouse.Tank_2, 0),
                                      (statics.Warehouse.Tank, 48)), 1):
        site.static(f"fuel tank {index}", kind, x, 15, objective=True)
    site.static("pump station", statics.Fortification.Pump_station, -58, 57)
    site.static("service office", statics.Fortification.Container_office, 63, 62)
    site.static("fuel transfer equipment", statics.Fortification.FARP_Fuel_Depot, -76, -28)
    site.static("generator", statics.Fortification.Container_generator, 78, 15)
    for index, (x, z) in enumerate(((-45, -26), (-27, -26), (-9, -26), (9, -26), (27, -26), (45, -26)), 1):
        site.static(f"fuel drums {index}", statics.Cargo.Barrels_cargo, x, z, jitter=2)
    site.static("fire equipment", statics.Fortification.FireExtinguisher01, 52, -18)
    site.static("maintenance toolbox", statics.Fortification.Toolbox01, -54, -46)
    site.static("spares crate", statics.Cargo.Cds_crate, 44, -48)
    _protective_screens(site)


def _command(site):
    site.static("headquarters", statics.Fortification._Command_Center, -27, 25, objective=True)
    site.static("operations office", statics.Fortification.Container_office, 41, 20, objective=True)
    site.static("communications mast", statics.Fortification.Comms_tower_M, -72, 50)
    for index, (x, z, kind) in enumerate(((-60, -20, statics.Fortification.Tent01),
                                         (-25, -20, statics.Fortification.Tent03),
                                         (12, -25, statics.Fortification.FARP_Tent)), 1):
        site.static(f"staff tent {index}", kind, x, z)
    site.static("generator", statics.Fortification.GeneratorF, 68, 42)
    site.static("camouflage shelter", statics.Fortification.Camouflage01, 35, 60)
    site.static("water supply", statics.Fortification.Fuel_tank, -76, 13)
    site.static("signal equipment", statics.Fortification.Container_10ft, -6, 62)
    for index, (x, z) in enumerate(((-66, -43), (-15, -43), (36, -43)), 1):
        site.static(f"supplies {index}", statics.Cargo.Cds_crate, x, z, jitter=2)
    site.static("checkpoint sandbags", statics.Fortification.Sandbag_01, 76, -72, angle=90)
    _protective_screens(site)


def _ammunition(site):
    site.static("ammunition storage", statics.Warehouse._Ammunition_depot, -37, 25, objective=True)
    site.static("supply store", statics.Fortification.Small_werehouse_1, 40, 25, objective=True)
    for index, (x, z) in enumerate(((-72, -20), (-45, -20), (-18, -20),
                                   (9, -20), (36, -20), (63, -20)), 1):
        site.static(f"ammunition pallets {index}", statics.Cargo.Ammo_cargo, x, z, jitter=2)
    site.static("covered ammunition", statics.Fortification.FARP_Ammo_Dump_Coating, -66, 62)
    site.static("shipping container", statics.Fortification.Container_20ft, 60, 62)
    site.static("packing crate", statics.Cargo.Cds_crate, -64, -43)
    site.static("rations", statics.Cargo.M92_MRE_Pallet, 35, -43)
    site.static("generator", statics.Fortification.GeneratorF, 80, 4)
    site.static("loading equipment", statics.Fortification.MJ_1_01, -80, 4)
    _container_perimeter(site)


def _factory(site):
    # Exactly one large workshop. Satellites never use this theme.
    site.static("repair works", statics.Fortification.Workshop_A, -32, 25, objective=True)
    site.static("vehicle garage", statics.Fortification.Garage_A, 57, 25, objective=True)
    site.static("maintenance shelter", statics.Fortification.Repair_workshop, -73, -22)
    site.static("excavator", statics.Fortification.X_345_Excavator, 18, -28)
    site.static("site office", statics.Fortification.Container_office, -72, 66)
    site.static("spares container", statics.Fortification.Container_20ft, 67, 68)
    site.static("pipe stack", statics.Cargo.Pipes_small_cargo, 60, -22)
    site.static("electrical equipment", statics.Fortification.Electric_power_box, 82, 4)
    site.static("generator", statics.Fortification.GeneratorF, -72, 25)
    for index, (x, z, kind) in enumerate(((-70, -43, statics.Cargo.Cds_crate),
                                         (-15, -25, statics.Cargo.Barrels_cargo),
                                         (45, -43, statics.Cargo.Iso_container_small),
                                         (15, 65, statics.Cargo.Cds_crate),
                                         (30, 65, statics.Cargo.Barrels_cargo)), 1):
        site.static(f"industrial supplies {index}", kind, x, z, jitter=2)
    _protective_screens(site)


def _radar(site):
    # Pydcs supports VehicleType as a static with category "Vehicles". This is
    # a destructible radar model, not an armed air-defence unit or active EWR.
    site.static("early warning radar", vehicles.vehicle_map["1L13 EWR"], 15, 25, objective=True)
    site.static("radar control office", statics.Fortification.Container_office, -52, 12, objective=True)
    site.static("communications mast", statics.Fortification.Comms_tower_M, 70, 55)
    site.static("power generator", statics.Fortification.Container_generator, -70, 55)
    site.static("technicians tent", statics.Fortification.Tent03, -48, -24)
    site.static("crew shelter", statics.Fortification.FARP_Tent, 15, -25)
    site.static("service container", statics.Fortification.Container_20ft, 38, 66)
    site.static("water supply", statics.Fortification.Fuel_tank, -72, 20)
    for index, (x, z, kind) in enumerate(((-65, -43, statics.Cargo.Cds_crate),
                                         (-15, -43, statics.Cargo.Barrels_cargo),
                                         (35, -43, statics.Cargo.Cds_crate),
                                         (72, -4, statics.Fortification.Toolbox02)), 1):
        site.static(f"radar spares {index}", kind, x, z, jitter=2)
    _protective_screens(site)


_BUILDERS = {"fuel": _fuel, "command": _command, "ammunition": _ammunition,
             "factory": _factory, "radar": _radar}


def build_facility_site(mission, country, point, rng, level, *, kind, index):
    """Build one occupied site with an explicit role and globally unique index."""
    if kind not in _BUILDERS:
        raise ValueError(f"Unknown site role: {kind}")
    heading = rng.uniform(0,360)
    site = _Site(mission, country, point, index, kind, heading, rng, level)
    _BUILDERS[kind](site)
    site.occupy()
    return site.metadata()


def build_facility_complex(mission, country, point, rng: random.Random, level: int,
                           *, facility_type: str = "random"):
    """Return ``(objective_static_names, primary_label, metadata)``.

    Difficulty levels 1–4 request 2/3/4/4 sites. The chosen facility determines
    the central site; satellites provide different support functions, never
    duplicate factories. Only the returned objective statics count as targets.
    No aircraft, SAM, AAA or MANPADS are created by this function.
    """
    if facility_type not in FACILITY_LABELS:
        raise ValueError(f"Unknown facility type: {facility_type!r}")
    if type(level) is not int or level not in (1, 2, 3, 4):
        raise ValueError("Facility difficulty level must be an integer from 1 to 4")
    kind = (rng.choice(("fuel", "fuel", "command", "command", "ammunition", "ammunition", "factory", "radar"))
            if facility_type == "random" else facility_type)
    requested = (2, 3, 4, 4)[level - 1]
    positions, notes = _site_positions(point, requested, rng)
    supports = [key for key in ("fuel", "command", "ammunition", "radar") if key != kind]
    rng.shuffle(supports)
    kinds = [kind, *supports][:len(positions)]
    sites = []
    objectives = []
    for index, (position, site_kind) in enumerate(zip(positions, kinds), 1):
        site = build_facility_site(mission, country, position, rng, level,
                                   kind=site_kind, index=index)
        objectives.extend(site["objective_statics"])
        sites.append(site)
    metadata = {
        "primary_type": kind, "style": _STYLES[kind],
        "requested_site_count": requested, "site_count": len(sites),
        "sites": sites, "styles": [site["style"] for site in sites],
        "objective_count": len(objectives),
        "decoration_count": sum(site["decoration_count"] for site in sites),
        "placement_notes": notes,
    }
    return objectives, FACILITY_LABELS[kind], metadata
