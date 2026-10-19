"""Faction equipment, helicopter sizing and saved DCS objective links."""
from dataclasses import replace
import json
import zipfile

import pytest
from dcs import lua, vehicles

from ironanvil.generator import build_mission, generate
from ironanvil.model import MissionOptions, resolve_aircraft
from ironanvil.opposition import (
    EQUIPMENT, FACTION_LABELS, enemy_country, fighter_type, ground_level, site_scale,
)
from ironanvil.recipes import read_recipe, write_recipe
from ironanvil.geography import distance_band


def groups(mission, category):
    return [group for country in mission.coalition['red'].countries.values()
            for group in getattr(country, category)]


@pytest.mark.parametrize('map_name', ('caucasus', 'syria', 'germany'))
@pytest.mark.parametrize('faction', FACTION_LABELS)
def test_factions_have_real_stock_equipment_and_armed_native_cap(map_name, faction):
    options = MissionOptions(map=map_name, opponent=faction, mission='line', difficulty='extreme',
        line_units=('mbt','ifv','apc','atgm','infantry','manpads','aaa','artillery'), seed=93)
    mission, metadata = build_mission(options)
    ground = enemy_country(mission, faction)
    assert metadata['opposition']['ground_country'] == ground.name
    assert ground in mission.coalition['red'].countries.values()
    assert ground not in mission.coalition['blue'].countries.values()
    assert ground.vehicle_group
    for role, choices in EQUIPMENT.get(faction, {}).items():
        if role not in ('truck', 'fuel', 'command', 'radar'):
            assert any(unit.type in choices for group in ground.vehicle_group for unit in group.units), role
    assert all(unit.type in vehicles.vehicle_map for group in ground.vehicle_group for unit in group.units)
    cap = groups(mission, 'plane_group')
    assert cap and all(g.late_activation and not g.uncontrolled for g in cap)
    assert all(u.type == fighter_type(options).id and u.pylons for g in cap for u in g.units)
    assert metadata['runtime']['cap_groups'] == [g.name for g in cap]
    assert any('Enemy: '+FACTION_LABELS[faction] in line for line in metadata['runtime']['briefing_lines'])
    assert mission.country('USA') in mission.coalition['blue'].countries.values()


@pytest.mark.parametrize('faction', FACTION_LABELS)
@pytest.mark.parametrize('helicopter', (False, True))
def test_disabled_threats_do_not_return_through_faction_conversion(faction, helicopter):
    mission, data = build_mission(MissionOptions(opponent=faction, mission='line', enemy_cap=False,
        aircraft='AH_64D_BLK_II' if helicopter else 'FA_18C_hornet', air_defenses=False,
        line_units=('infantry','manpads','aaa'), seed=43))
    types = {u.type for g in groups(mission, 'vehicle_group') for u in g.units}
    assert types <= {'Infantry AK','Infantry AK Ins','Soldier M4','Soldier M249'}
    assert not groups(mission, 'plane_group')
    assert not data['runtime']['cap_groups']


@pytest.mark.parametrize('aircraft', ('AH_64D_BLK_II','Ka_50','Mi_24P','UH_1H'))
def test_helicopter_scale_is_automatic_for_each_aircraft(aircraft):
    options = MissionOptions(aircraft=aircraft, operation='broken_relay', enemy_cap=False,
        start='air', pace='compact', seed=91)
    mission, data = build_mission(options)
    assert data['opposition']['scale'] == 'helicopter'
    assert data['opposition']['ground_level'] == 1
    assert 6.4 <= data['geography']['distance_km'] <= 9.6
    assert len(data['facility_sites']) == 2
    assert all(site['garrison_units'] == 3 for site in data['facility_sites'])
    first, second = data['facility_sites']
    assert 1500 <= ((first['x']-second['x'])**2+(first['z']-second['z'])**2)**.5 <= 2500
    red = enemy_country(mission, options.opponent)
    response = next(g for g in red.vehicle_group if g.name == 'OPERATION RESPONSE')
    assert len(response.units) == 2
    defenses = next(g for g in red.vehicle_group if g.name == 'AIR DEFENSE SITE 1')
    assert [u.type for u in defenses.units] == ['Ural-375 ZU-23']
    assert not data['runtime']['cap_groups']


@pytest.mark.parametrize('faction,aaa,manpads', (
    ('regular', {'Ural-375 ZU-23','ZSU-23-4 Shilka'}, {'SA-18 Igla manpad'}),
    ('syrian', {'Ural-375 ZU-23','ZSU-23-4 Shilka'}, {'SA-18 Igla manpad'}),
    ('western', {'Vulcan'}, {'Soldier stinger'}),
    ('insurgents', {'tt_ZU-23','Ural-375 ZU-23 Insurgent'}, {'Igla manpad INS'}),
))
def test_helo_defenses_escalate_without_default_sam_rings(faction, aaa, manpads):
    for difficulty in ('easy','normal','hard','extreme'):
        m, data = build_mission(MissionOptions(opponent=faction, difficulty=difficulty,
            aircraft='AH_64D_BLK_II', mission='convoy', enemy_cap=True, seed=19))
        defense_types = {u.type for g in groups(m, 'vehicle_group') if 'AIR DEFENSE' in g.name for u in g.units}
        assert defense_types & aaa or difficulty == 'extreme'
        if difficulty in ('easy','normal'):
            assert defense_types <= aaa
        elif difficulty == 'hard':
            assert defense_types & manpads
            assert defense_types <= aaa | manpads
        assert groups(m, 'plane_group')  # Explicit CAP remains enabled, including militia.
        assert data['runtime']['cap_groups']


@pytest.mark.parametrize('faction', FACTION_LABELS)
def test_saved_helo_operation_replays_and_keeps_all_objective_unit_links(tmp_path, faction):
    options = MissionOptions(opponent=faction, aircraft='AH_64D_BLK_II', operation='rolling_thunder',
        start='air', seed=791, enemy_cap=True, air_defenses=False)
    path = generate(options, tmp_path / (faction+'.miz'))
    assert read_recipe(path) == options
    assert read_recipe(write_recipe(options, tmp_path/(faction+'.json'))) == options
    with zipfile.ZipFile(path) as archive:
        data = json.loads(archive.read('ironanvil.json'))
        saved = lua.loads(archive.read('mission').decode())['mission']
        assert FACTION_LABELS[faction] in archive.read('ironanvil-briefing.html').decode()
    red = saved['coalition']['red']['country'].values()
    units = {u['name']:u for c in red for g in c.get('vehicle',{}).get('group',{}).values()
             for u in g['units'].values()}
    primary = data['runtime']['operation']['objectives'][0]
    assert primary['threshold'] == 2 and len(primary['units']) == 3
    supply = [units[name]['type'] for name in primary['units']]
    assert all(kind in ('Ural-375','Ural ATsP-6','M 818','M978 HEMTT Tanker') for kind in supply)
    assert set(data['opposition']['ground_types']) == {u['type'] for u in units.values()}
    assert not any('AIR DEFENSE' in u['name'] for u in units.values())


def test_helicopter_scaling_preserves_explicit_pin_factory_and_tanks():
    options = MissionOptions(aircraft='AH_64D_BLK_II', target_lat=42.1, target_lon=42.35,
        facility_type='factory', enemy_cap=False, air_defenses=False)
    _, data = build_mission(options)
    assert data['facility_type'] == 'factory'
    assert len(data['facility_sites']) == 2
    assert (data['target_lat'],data['target_lon']) == (42.1,42.35)
    mission, _ = build_mission(replace(options, mission='line', line_units=('mbt',)))
    assert all(u.type == 'T-72B' for g in groups(mission,'vehicle_group') for u in g.units)


def test_fixed_wing_defaults_keep_existing_distances_and_ground_level():
    options = MissionOptions()
    assert ground_level(options) == 2 and site_scale(options) == 1
    assert distance_band(resolve_aircraft(options.aircraft),'standard') == (48000,72000)


def test_insurgent_convoy_escorts_drive_instead_of_walking_with_trucks():
    mission, _ = build_mission(MissionOptions(opponent='insurgents', mission='convoy',
        aircraft='AH_64D_BLK_II', enemy_cap=False, air_defenses=False))
    convoy = next(g for g in groups(mission,'vehicle_group') if g.name == 'OBJECTIVE CONVOY')
    assert any(u.type == 'tt_KORD' for u in convoy.units)
    assert not any('Infantry' in u.type for u in convoy.units)


@pytest.mark.parametrize('faction,defenses', (('insurgents', True), ('regular', False)))
def test_recommended_sead_weapons_can_hit_non_radar_targets(faction, defenses):
    _, data = build_mission(MissionOptions(mission='sead', opponent=faction,
        air_defenses=defenses, enemy_cap=False))
    stores = [store['name'].lower() for store in data['loadout']['stores']]
    assert any('gbu' in name for name in stores)
    assert not any('harm' in name for name in stores)
