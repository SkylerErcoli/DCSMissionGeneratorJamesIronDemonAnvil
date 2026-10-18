"""Small, self-contained operations for friends flying the same aircraft together."""
from __future__ import annotations

from dcs import vehicles
from dcs.unit import Skill

from .compounds import build_facility_site, FACILITY_LABELS

OPERATION_LABELS = {
    'classic': 'Classic single mission',
    'broken_relay': 'Operation Broken Relay',
    'supply_denial': 'Operation Supply Denial',
    'rolling_thunder': 'Operation Rolling Thunder',
}
OPERATION_HELP = {
    'classic': 'The original mission rules. Choose any mission type below.',
    'broken_relay': 'Disable the fuel depot. Take out communications first to delay the enemy response. Same aircraft, shared goals.',
    'supply_denial': 'Disable the ammunition depot. Destroy the fuel support site before dispatch to cancel the enemy response.',
    'rolling_thunder': 'Intercept three moving supply trucks. Stop two before delivery for an extra bonus. Fuel support can cancel the ground response.',
}
PACE_LABELS = {'compact': 'Close to base', 'standard': 'Standard distance', 'extended': 'Longer sortie'}


def _suitable(point, theatre, *, footprint=170):
    for bearing in range(0, 360, 45):
        location = point.point_from_heading(bearing, footprint).latlng()
        if not theatre.contains(location.lat, location.lng) or not theatre.is_land(location.lat, location.lng):
            return False
    coordinates = point.latlng()
    return theatre.contains(coordinates.lat, coordinates.lng) and theatre.is_land(coordinates.lat, coordinates.lng)


def choose_target(home, preferred, theatre, aircraft, pace, rng):
    """Choose a land footprint at an aircraft-appropriate distance, never a time guarantee."""
    distances = (10000, 22000, 38000) if aircraft.helicopter else (28000, 60000, 100000)
    distance = distances[('compact', 'standard', 'extended').index(pace)]
    heading = home.position.heading_between_point(preferred) + rng.uniform(-25, 25)
    for fraction in (1, .85, .65):
        for turn in (0, 20, -20, 40, -40, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            point = home.position.point_from_heading(heading + turn, distance * fraction)
            if _suitable(point, theatre):
                return point
    raise ValueError('No suitable inland target at this distance. Pin a target inland or choose another departure base.')


def _separate_site(point, home, theatre, rng, *, distance):
    heading = point.heading_between_point(home.position) + rng.uniform(-35, 35)
    for scale in (1, 1.25, 1.6):
        for turn in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            candidate = point.point_from_heading(heading + turn, distance * scale)
            if candidate.distance_to_point(home.position) < 3000:
                continue
            if _suitable(candidate, theatre):
                return candidate
    raise ValueError('This target has no room for separated operation sites. Pin a point farther inland.')


def build_operation(mission, country, target, home, theatre, options, rng, level):
    relay = options.operation == 'broken_relay'
    rolling = options.operation == 'rolling_thunder'
    primary_kind, bonus_kind = ('fuel', 'command') if relay else ('command' if rolling else 'ammunition', 'fuel')
    separation = {'compact': 2400, 'standard': 3800, 'extended': 6000}[options.pace]
    secondary = _separate_site(target, home, theatre, rng, distance=separation)
    sites = [build_facility_site(mission, country, target, rng, level, kind=primary_kind, index=1),
             build_facility_site(mission, country, secondary, rng, level, kind=bonus_kind, index=2)]
    # The real facilities supply the names; no decorative object is mandatory.
    primary_names = sites[0]['objective_statics']
    bonus_names = sites[1]['objective_statics']
    threshold = 2 if primary_kind == 'fuel' else 1
    effect = 'delay' if relay else 'cancel'
    objective = {
        'id': options.operation, 'title': OPERATION_LABELS[options.operation], 'seed': options.seed,
        'objectives': [
            {'id': 'primary', 'title': FACILITY_LABELS[primary_kind], 'required': True,
             'statics': primary_names, 'threshold': threshold, 'points': 300,
             'position': {'x': target.x, 'z': target.y}},
            {'id': 'bonus', 'title': FACILITY_LABELS[bonus_kind], 'required': False,
             'statics': bonus_names, 'threshold': 1, 'points': 100, 'effect': effect,
             'position': {'x': secondary.x, 'z': secondary.y}},
        ],
    }
    if rolling:
        destination = _separate_site(target, home, theatre, rng, distance=7500)
        types = ['Ural-375', 'Ural ATsP-6', 'Ural-375',
                 'BTR-60' if options.opponent == 'insurgents' else 'BTR-80']
        if options.air_defenses:
            types.append('Ural-375 ZU-23 Insurgent' if options.opponent == 'insurgents' else 'Ural-375 ZU-23')
        convoy = mission.vehicle_group_platoon(country, 'OPERATION SUPPLY CONVOY',
                    [vehicles.vehicle_map[t] for t in types], target, heading=target.heading_between_point(destination))
        convoy.set_skill((Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[level - 1])
        convoy.add_waypoint(destination, speed=30)
        objective['objectives'][0].update(title='Moving supply convoy', statics=[],
            units=[unit.name for unit in convoy.units[:3]], group=convoy.name, threshold=2)
        objective['convoy'] = {'group': convoy.name, 'destination': {'x': destination.x, 'z': destination.y},
            'delivery_radius': 350, 'interdiction_points': 150, 'delivery_response_delay': 60}
    if options.enemy_response:
        staging = _separate_site(target, home, theatre, rng, distance=9000)
        types = (['BTR-60', 'Ural-375'] if options.opponent == 'insurgents' else
                 ['BTR-80', 'Ural-375'] if level == 1 else ['BMP-2', 'BTR-80', 'Ural-375'])
        if level >= 3:
            types.append('BMP-2')
        response = mission.vehicle_group_platoon(country, 'OPERATION RESPONSE',
                    [vehicles.vehicle_map[t] for t in types], staging, heading=staging.heading_between_point(target))
        response.set_skill((Skill.Average, Skill.Good, Skill.High, Skill.Excellent)[level - 1])
        # A valid editor route remains visible and editable; Lua holds this group
        # at mission start and issues a road-aware route only after dispatch.
        response.add_waypoint(target, speed=30)
        response_destination = objective['convoy']['destination'] if rolling else {'x': target.x, 'z': target.y}
        objective['response'] = {'group': response.name, 'destination': response_destination,
            'staging': {'x': staging.x, 'z': staging.y},
            'delay': (300, 180, 150, 120)[level - 1] + rng.randrange(31),
            'bonus_delay': 360, 'max_attempts': 3, 'retry_interval': 15}
    metadata = {'primary_type': primary_kind, 'style': 'linked cooperative operation',
                'requested_site_count': 2, 'site_count': 2, 'sites': sites,
                'styles': [s['style'] for s in sites],
                'objective_count': sum(s['objective_count'] for s in sites),
                'decoration_count': sum(s['decoration_count'] for s in sites), 'placement_notes': []}
    return objective, metadata


def operation_briefing(operation):
    lines = [operation['title'].upper(), 'COOPERATIVE OPERATION — all pilots share the same objectives.',
             'Choose either site first. Optional tasks never block mission completion.']
    for objective in operation['objectives']:
        role = 'REQUIRED' if objective['required'] else 'BONUS'
        total = len(objective.get('statics', [])) + len(objective.get('units', []))
        kind = 'supply trucks' if objective.get('units') else 'objective structures'
        lines.append(f"{role}: {objective['title']} — disable {objective['threshold']} of {total} {kind}. Guards and scenery do not count.")
    if operation.get('convoy'):
        lines.extend(['The supply convoy departs when a client is airborne. F10 target position follows the live convoy.',
                      'Stop two supply trucks before delivery for 150 extra shared points. Escorts are not mandatory targets.',
                      'Delivery does not fail the mission, but a surviving convoy can accelerate a still-preparing response to one minute.'])
    response = operation.get('response')
    if response:
        lines.extend([
            f"The first damage to either site raises the alarm. One finite ground response can dispatch after {response['delay']} seconds, then must travel to the main site.",
            ('Disable communications before dispatch to add six minutes to the response delay.'
             if operation['id'] == 'broken_relay' else
             'Disable the bonus fuel site before dispatch to cancel the response. A force already dispatched will not disappear.'),
            'You may intercept the preplaced response force. No endless waves or reinforcements spawning beside you.',
        ])
    else:
        lines.append('Ground response is disabled. The optional site still earns a bonus.')
    lines.extend(['After the required objective is disabled, return to home base. You may complete the bonus before recovering.',
                  'F10 > Iron Anvil > Operation status shows individual goals and the response state.',
                  'Main objective: 300 points; bonus: 100; each surviving client recovered: 25. Score is shared, not a kill contest.',
                  f"Replay seed: {operation['seed']}."])
    return '\n\n'.join(lines)
