"""Small desktop shortcuts over existing mission options, not another ruleset."""
SCENARIOS = {
    'broken_relay': ('Broken Relay · fuel strike', 'facility', 'broken_relay',
        'Disable two fuel tanks. The optional command site delays the ground response.'),
    'supply_denial': ('Supply Denial · ammo strike', 'facility', 'supply_denial',
        'Disable an ammunition structure. Optional fuel support can cancel the ground response.'),
    'rolling_thunder': ('Rolling Thunder · convoy hunt', 'facility', 'rolling_thunder',
        'Stop two cargo trucks. Intercept them before delivery for a bonus.'),
    'facility': ('Facility strike', 'facility', 'classic', 'Destroy the installation and its supporting sites.'),
    'line': ('Fortified positions', 'line', 'classic', 'Attack the troops and vehicles in staggered sandbag positions.'),
    'convoy': ('Convoy strike', 'convoy', 'classic', 'Destroy the moving enemy convoy. F10 updates its position.'),
    'sead': ('Destroy air defenses', 'sead', 'classic', 'Destroy enemy air defenses. With air defenses off, attack their support vehicles.'),
    'cap': ('Air patrol', 'cap', 'classic', 'Defeat enemy fighters, or fly a five-minute patrol if enemy fighters are off.'),
}
PRESSURES = {
    'Relaxed': {'difficulty': 'easy', 'enemy_cap': False, 'air_defenses': False, 'response': False},
    'Balanced': {'difficulty': 'normal', 'enemy_cap': False, 'air_defenses': True, 'response': True},
    'Challenging': {'difficulty': 'hard', 'enemy_cap': True, 'air_defenses': True, 'response': True},
}
PRESSURE_HELP = {
    'Relaxed': 'No enemy fighters, anti-air defenses or ground response. Ground troops remain armed.',
    'Balanced': 'Air defenses and one ground response; enemy fighters only for air patrols.',
    'Challenging': 'Enemy fighters, air defenses and a ground response, with more skilled enemies.',
    'Custom': 'Your individual threat settings are active. Change either switch below or use Customize.',
}
START_HELP = {'cold': 'Parked, engines off', 'hot': 'Parked, engines running',
              'runway': 'Ready on the runway', 'air': 'Already airborne'}
LOADOUT_LABELS = {'auto': 'Recommended weapons', 'default': 'DCS local preset (may be empty)'}


def pressure_settings(label, mission):
    values=PRESSURES[label].copy()
    if mission=='cap' and label!='Relaxed':values['enemy_cap']=True
    return values


def pressure_name(settings, mission):
    return next((label for label in PRESSURES if pressure_settings(label,mission)==settings),'Custom')
