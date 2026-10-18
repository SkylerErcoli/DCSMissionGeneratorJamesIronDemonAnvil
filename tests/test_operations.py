"""Inspect actual saved operations: shared goals, finite forces and safe defaults."""
from dataclasses import replace
import json
import math
import zipfile

from dcs import Mission
import pytest

from ironanvil.generator import build_mission, generate, PLAYER_GROUP
from ironanvil.model import MissionOptions
from ironanvil.theatres import get_theatre

AD_TYPES={'Osa 9A33 ln','Kub 1S91 str','Kub 2P25 ln','SA-18 Igla manpad',
          'ZSU-23-4 Shilka','Ural-375 ZU-23','Ural-375 ZU-23 Insurgent','Igla manpad INS'}


@pytest.mark.parametrize('terrain', ['caucasus','syria','germany'])
@pytest.mark.parametrize('operation', ['broken_relay','supply_denial'])
@pytest.mark.parametrize('threats', [False,True])
def test_saved_coop_operations_are_complete_and_respect_threat_switches(tmp_path,terrain,operation,threats):
    path=generate(MissionOptions(map=terrain,operation=operation,clients=4,seed=37,
        enemy_cap=threats,air_defenses=threats,tanker=True,awacs=True), tmp_path/'operation.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        script=archive.read('l10n/DEFAULT/ironanvil_runtime.lua').decode()
        assert 'IRON_ANVIL_CREATE_OPERATION = function' in script
        assert script.index('IRON_ANVIL_CREATE_OPERATION = function') < script.index('local config = IRON_ANVIL')
        assert archive.testzip() is None
    mission=Mission();mission.load_file(str(path))
    config=metadata['runtime']['operation']
    required,bonus=config['objectives']
    assert required['required'] and not bonus['required']
    assert required['threshold']==(2 if operation=='broken_relay' else 1)
    assert bonus['effect']==('delay' if operation=='broken_relay' else 'cancel')
    statics={u.name for g in mission.country('Russia').static_group for u in g.units}
    for goal in config['objectives']:
        assert set(goal['statics']) <= statics
        assert 0 < goal['threshold'] <= len(goal['statics'])
    decor={n for site in metadata['facility_sites'] for n in site['decoration_statics']}
    assert not decor.intersection(n for goal in config['objectives'] for n in goal['statics'])
    assert sum(site['garrison_units'] for site in metadata['facility_sites']) >= 8
    first,second=metadata['facility_sites']
    assert math.hypot(first['x']-second['x'],first['z']-second['z']) >= 2000
    response=[g for g in mission.country('Russia').vehicle_group if g.name=='OPERATION RESPONSE']
    assert len(response)==1 and len(response[0].units) <= 4
    assert len(response[0].points)>=2
    redtypes={u.type for g in mission.country('Russia').vehicle_group for u in g.units}
    assert bool(redtypes & AD_TYPES) is threats
    assert bool(metadata['runtime']['cap_groups']) is threats
    flight=next(g for g in mission.country('USA').plane_group if g.name==PLAYER_GROUP)
    assert len(flight.units)==4 and all(u.skill.value=='Client' for u in flight.units)
    assert mission.terrain.airport_by_id(metadata['home_airport_id']).is_blue()


@pytest.mark.parametrize('operation', ['broken_relay','supply_denial'])
def test_response_can_be_disabled_without_losing_bonus_goal(operation):
    mission,metadata=build_mission(MissionOptions(operation=operation,enemy_response=False))
    assert 'response' not in metadata['runtime']['operation']
    assert not any(g.name=='OPERATION RESPONSE' for g in mission.country('Russia').vehicle_group)
    assert len(metadata['runtime']['operation']['objectives'])==2


@pytest.mark.parametrize('aircraft', ['FA_18C_hornet','AH_64D_BLK_II','P_51D','A_10C'])
def test_same_aircraft_coop_does_not_require_extra_modules(aircraft):
    mission,metadata=build_mission(MissionOptions(operation='broken_relay',aircraft=aircraft,
        enemy_cap=False,air_defenses=False,clients=2,start='air'))
    blue=mission.country('USA')
    clients=[u for g in blue.plane_group+blue.helicopter_group for u in g.units if u.skill.value=='Client']
    assert len(clients)==2 and len({u.type for u in clients})==1
    assert metadata['runtime']['operation']['id']=='broken_relay'


def test_sortie_distance_scales_for_aircraft_and_pinned_target_is_preserved():
    distances=[]
    for pace in ('compact','standard','extended'):
        _,metadata=build_mission(MissionOptions(operation='broken_relay',pace=pace,seed=5))
        distances.append(metadata['route_summary']['one_way_km'])
    assert distances==sorted(distances) and distances[-1] >= 2*distances[0]
    _,helo=build_mission(MissionOptions(operation='broken_relay',aircraft='AH_64D_BLK_II',pace='compact'))
    assert helo['route_summary']['one_way_km'] < distances[0]
    options=MissionOptions(operation='broken_relay',pace='extended',target_lat=42.1,target_lon=42.35)
    _,pinned=build_mission(options)
    assert (pinned['target_lat'],pinned['target_lon'])==(42.1,42.35)


def test_operation_choices_are_validated_and_seed_replays():
    for change in ({'operation':'unknown'},{'pace':'unknown'},{'enemy_response':'yes'},
                   {'operation':'broken_relay','mission':'cap'}):
        with pytest.raises(ValueError):replace(MissionOptions(),**change).validate()
    options=MissionOptions(operation='broken_relay',seed=153,map='germany')
    _,first=build_mission(options);_,second=build_mission(options)
    assert first==second


def test_classic_missions_keep_legacy_goal_rules():
    _,metadata=build_mission(MissionOptions())
    assert metadata['runtime']['operation'] is None
    assert len(metadata['facility_sites'])==3
    assert metadata['runtime']['target_statics']==[name for site in metadata['facility_sites'] for name in site['objective_statics']]


@pytest.mark.parametrize('terrain',['caucasus','syria','germany'])
@pytest.mark.parametrize('threats',[False,True])
def test_rolling_thunder_saved_convoy_has_three_supply_targets_and_optional_escorts(tmp_path,terrain,threats):
    path=generate(MissionOptions(map=terrain,operation='rolling_thunder',enemy_cap=threats,
        air_defenses=threats,clients=2,seed=81),tmp_path/'convoy-operation.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        assert archive.testzip() is None
        assert b'supply trucks' in archive.read('ironanvil-briefing.html')
    mission=Mission();mission.load_file(str(path))
    operation=metadata['runtime']['operation'];goal=operation['objectives'][0]
    convoy=mission.coalition['red'].find_group(operation['convoy']['group'])
    assert goal['required'] and goal['threshold']==2 and len(goal['units'])==3 and goal['statics']==[]
    assert set(goal['units'])=={unit.name for unit in convoy.units[:3]}
    assert all(unit.type in ('Ural-375','Ural ATsP-6') for unit in convoy.units[:3])
    assert metadata['runtime']['convoy_group']==convoy.name and len(convoy.points)>=2
    assert bool({unit.type for unit in convoy.units}&AD_TYPES) is threats
    assert metadata['runtime']['convoy_destination']==operation['convoy']['destination']
    assert len(operation['objectives'])==2 and not operation['objectives'][1]['required']
    assert len(convoy.units) <= 5
