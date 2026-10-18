"""Complete airborne AI routes for tankers, AWACS and hostile patrols.

The pinned pydcs API accepts km/h for flight creation, route waypoints AND
OrbitAction, and converts all three to m/s in the saved mission.  Keep these
inputs in km/h; a second conversion would give the AI a dangerously low speed.
"""
from __future__ import annotations

import math

from dcs import action, condition, task, triggers
from dcs.unit import Skill

from .loadouts import apply_loadout


CAP_LAUNCH_FLAG = "IRON_ANVIL_CAP_LAUNCH_REQUESTED"


def add_cap_launch_triggers(mission, clients, cap_groups):
    """Let DCS activate CAP directly when any client climbs above 30 m AGL.

    Native unit-ID conditions and group-ID actions work independently of the
    Lua controller's takeoff events, group lookups and activation wrapper.
    The shared latch keeps later client departures from restarting the patrol.
    """
    if not cap_groups:
        return
    for client in clients.units:
        launch = triggers.TriggerOnce(comment=f"Iron Anvil CAP launch - client {client.id}")
        launch.add_condition(condition.FlagIsFalse(CAP_LAUNCH_FLAG))
        launch.add_condition(condition.UnitAltitudeHigherAGL(client.id, 30))
        for group in cap_groups:
            launch.add_action(action.ActivateGroup(group.id))
        launch.add_action(action.SetFlag(CAP_LAUNCH_FLAG))
        mission.triggerrules.triggers.append(launch)


def _align_airborne_group(group, destination):
    """Give the spawned aircraft an attitude consistent with its first leg."""
    heading = group.units[0].position.heading_between_point(destination)
    for unit in group.units:
        unit.heading = heading
        unit.psi = -math.radians(heading)
        unit.alt_type = "BARO"
        unit.fuel = unit.unit_type.fuel_max
    for index, waypoint in enumerate(group.points):
        waypoint.alt_type = "BARO"
        # DCS requires a time reference on every flight route, and specifically
        # the first waypoint for late activation. Keep the spawn at time zero;
        # subsequent legs use cruise speed rather than fixed arrival times.
        waypoint.ETA_locked = index == 0
        if index == 0:
            waypoint.ETA = 0


def create_support_flight(mission, country, name, aircraft, point, main_task, frequency,
                          *, altitude=7000, speed_kph=None, heading=90, tacan_channel=11):
    """Create an immediately active support aircraft with a complete racetrack.

    ``point`` is the first orbit anchor.  The AI spawns eight kilometres before
    that anchor, flies straight and level into its orbit, then uses a second
    anchor 25 kilometres ahead.  A racetrack without that following waypoint
    leaves DCS without a valid second turn point.
    """
    if main_task not in (task.Refueling, task.AWACS):
        raise ValueError("Support aircraft must have a Refueling or AWACS task")
    if main_task not in aircraft.tasks:
        raise ValueError(f"{aircraft.id} does not support {main_task.name}")
    if altitude < 6500:
        raise ValueError("Support altitude must be at least 6500 metres MSL")
    if speed_kph is None:
        speed_kph = 500 if aircraft.__name__ == "KC130" else 650
    if not 400 <= speed_kph <= min(800, aircraft.max_speed):
        raise ValueError("Support speed must be a safe cruise speed in km/h")

    origin = point.point_from_heading((heading + 180) % 360, 8000)
    far_anchor = point.point_from_heading(heading % 360, 25000)
    group = mission.flight_group_inflight(
        country, name, aircraft, origin, altitude, speed_kph,
        maintask=main_task, group_size=1,
    )
    group.frequency = frequency
    group.late_activation = False
    group.uncontrolled = False
    group.set_skill(Skill.Excellent)
    first = group.points[0]
    # pydcs inserts the Tanker/AWACS role at the initial point. Keep that role
    # active while the aircraft flies its lead-in and then its orbit.
    first.tasks.extend((
        # DCS "invisible" suppresses AI detection, while retaining the visible
        # aircraft, its tanker/AWACS role and radio interaction for human pilots.
        task.SetInvisibleCommand(True),
        task.SetImmortalCommand(True),
        task.OptROE(task.OptROE.Values.WeaponHold),
        task.OptReactOnThreat(task.OptReactOnThreat.Values.EvadeFire),
        task.OptRTBOnBingoFuel(False),
        task.SetUnlimitedFuelCommand(True),
    ))
    if main_task == task.Refueling and tacan_channel is not None:
        if not 1 <= tacan_channel <= 126:
            raise ValueError("TACAN channel must be between 1 and 126")
        first.tasks.append(task.ActivateBeaconCommand(
            channel=tacan_channel, modechannel="Y", callsign="TEX",
            unit_id=group.units[0].id, aa=True,
        ))
    anchor = group.add_waypoint(point, altitude, speed_kph, name="SUPPORT ORBIT START")
    anchor.tasks.append(task.OrbitAction(
        altitude=altitude, speed=speed_kph, pattern=task.OrbitAction.OrbitPattern.RaceTrack,
    ))
    group.add_waypoint(far_anchor, altitude, speed_kph, name="SUPPORT ORBIT END")
    _align_airborne_group(group, point)
    return group


def create_enemy_cap(mission, country, name, aircraft, spawn, station, *,
                     group_size=2, skill=Skill.Good, late_activation=True,
                     altitude=6500, speed_kph=800):
    """Create armed fighters which can search and engage from activation.

    Activation timing is controlled separately by the mission runtime.  The
    first point already contains the engagement task, rather than waiting
    until the fighters arrive at the target station to become useful.
    """
    if task.CAP not in aircraft.tasks:
        raise ValueError(f"{aircraft.id} does not support CAP")
    group = mission.flight_group_inflight(
        country, name, aircraft, spawn, altitude, speed_kph,
        maintask=task.CAP, group_size=group_size,
    )
    group.late_activation = late_activation
    group.uncontrolled = False
    group.set_skill(skill)
    apply_loadout(group, "cap")
    first = group.points[0]
    first.tasks.extend((
        task.OptROE(task.OptROE.Values.WeaponFree),
        task.OptRadarUsing(task.OptRadarUsing.Values.UseForContinuousSearch),
        task.OptReactOnThreat(task.OptReactOnThreat.Values.EvadeFire),
        task.EngageTargets(max_distance=100000, targets=[task.Targets.All.Air]),
    ))
    intercept = group.add_waypoint(station, altitude, speed_kph, name="INTERCEPT / CAP STATION")
    intercept.tasks.append(task.OrbitAction(
        altitude=altitude, speed=speed_kph, pattern=task.OrbitAction.OrbitPattern.Circle,
    ))
    # A complete onward leg avoids ending the group's route at the hold point.
    # The indefinite circle normally keeps this fallback point unreached.
    onward_heading = spawn.heading_between_point(station)
    group.add_waypoint(station.point_from_heading(onward_heading, 30000),
                       altitude, speed_kph, name="CAP CONTINUATION")
    _align_airborne_group(group, station)
    return group
