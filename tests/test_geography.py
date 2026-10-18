"""Verify varied planning, exact user constraints and public terrain screening."""
from dataclasses import replace
import random
from collections import Counter

import pytest
from dcs import mapping

from ironanvil.geography import plan_scenario, suitable_ground, public_land, height_at, distance_band
from ironanvil.model import MissionOptions, resolve_aircraft
from ironanvil.theatres import get_theatre


@pytest.mark.parametrize('map,minimum_homes',[('caucasus',15),('syria',30),('germany',40)])
def test_automatic_planning_covers_regions_bearings_and_distance_ranges(map,minimum_homes):
    theatre=get_theatre(map);terrain=theatre.terrain();aircraft=resolve_aircraft('FA_18C_hornet')
    homes=set();positions=set();sectors=Counter();distances=[]
    for seed in range(300):
        options=MissionOptions(map=map,seed=seed) # classic standard formerly always fixed
        scenario=plan_scenario(options,theatre,terrain,aircraft,random.Random(seed))
        homes.add(scenario.home.id);positions.add((round(scenario.target.x),round(scenario.target.y)))
        sectors[int(scenario.metadata['heading_grid']//45)]+=1
        distance=scenario.home.position.distance_to_point(scenario.target);distances.append(distance)
        low,high=distance_band(aircraft,options.pace)
        assert low<=distance<=high
        assert suitable_ground(scenario.target,theatre,airports=terrain.airports.values())
    assert len(homes)>=minimum_homes and len(positions)==300
    assert set(sectors)==set(range(8))
    assert max(distances)-min(distances)>15000


@pytest.mark.parametrize('map',['caucasus','syria','germany'])
@pytest.mark.parametrize('aircraft',['FA_18C_hornet','AH_64D_BLK_II'])
def test_seeded_plan_and_local_ownership_are_reproducible_and_recovery_is_friendly(map,aircraft):
    theatre=get_theatre(map);terrain=theatre.terrain();aircraft=resolve_aircraft(aircraft)
    options=MissionOptions(map=map,aircraft=aircraft.__name__,pace='compact',recovery='home_or_alternate',seed=72)
    a=plan_scenario(options,theatre,terrain,aircraft,random.Random(72))
    b=plan_scenario(options,theatre,terrain,aircraft,random.Random(72))
    assert a.metadata==b.metadata and a.ownership==b.ownership
    assert (a.home.id,a.target.x,a.target.y,a.alternate.id)==(b.home.id,b.target.x,b.target.y,b.alternate.id)
    assert a.ownership[a.home.id]==a.ownership[a.alternate.id]=='blue'
    assert a.home.id!=a.alternate.id and 'red' in a.ownership.values()
    for airport in (a.home,a.alternate):assert len(airport.free_parking_slots(aircraft))>=2
    assert a.home.position.distance_to_point(a.alternate.position)<=120000


@pytest.mark.parametrize('map,name',[('caucasus','Anapa-Vityazevo'),('syria','Damascus'),('germany','Stendal')])
def test_explicit_departure_and_pin_override_random_planning(map,name):
    theatre=get_theatre(map);terrain=theatre.terrain();aircraft=resolve_aircraft('FA_18C_hornet')
    lat,lon=theatre.default_target
    options=MissionOptions(map=map,departure_airport=name,target_lat=lat,target_lon=lon,pace='extended')
    for seed in (1,41):
        plan=plan_scenario(options,theatre,terrain,aircraft,random.Random(seed))
        expected=mapping.Point.from_latlng(mapping.LatLng(lat,lon),terrain)
        assert plan.home.name==name and plan.target.distance_to_point(expected)<.001


@pytest.mark.parametrize('map,lat,lon,height_range',[
    ('germany',52.52,13.4,(0,100)),('caucasus',43.35,42.44,(3500,6000)),
    ('syria',33.42,35.85,(1800,3100)),
])
def test_public_elevation_has_real_plausible_values_and_mountains_are_screened(map,lat,lon,height_range):
    theatre=get_theatre(map);height=height_at(theatre,lat,lon)
    assert height_range[0]<=height<=height_range[1]
    point=mapping.Point.from_latlng(mapping.LatLng(lat,lon),theatre.terrain())
    if height>1800:assert not suitable_ground(point,theatre)


@pytest.mark.parametrize('map,lat,lon',[('germany',53.42,12.68),('syria',32.82,35.59),('caucasus',43,36)])
def test_lakes_and_sea_are_excluded_by_offline_detailed_land_mask(map,lat,lon):
    assert not public_land(get_theatre(map),lat,lon)


def test_coastal_operation_plans_all_sites_before_accepting_target():
    # Previously accepted a small flat primary patch, then failed to fit its bonus.
    theatre=get_theatre('caucasus');terrain=theatre.terrain();aircraft=resolve_aircraft('FA_18C_hornet')
    options=MissionOptions(operation='broken_relay',pace='compact',seed=4)
    plan=plan_scenario(options,theatre,terrain,aircraft,random.Random(4))
    assert set(plan.sites)=={'secondary','staging'}
    for point in plan.sites.values():
        assert suitable_ground(point,theatre,footprint=170,airports=terrain.airports.values())
        assert point.distance_to_point(plan.home.position)>3000
