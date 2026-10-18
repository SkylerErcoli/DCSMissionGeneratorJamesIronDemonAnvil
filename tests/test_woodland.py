"""Real source-data samples, complete footprints and actual placed ground units."""
import hashlib
import json
from types import SimpleNamespace

import pytest
from PIL import Image
from dcs import mapping

from ironanvil import geography
from ironanvil.generator import build_mission
from ironanvil.model import MissionOptions
from ironanvil.theatres import THEATRES


@pytest.mark.parametrize('key,wooded,open_point',[
    ('caucasus',(41.9,43.1),(42.15,41.65)),  # Borjomi woodland / Poti
    ('syria',(32.25,35.81),(35.2,37.0)),     # Dibbin woodland / cultivated land
    ('germany',(52.475,13.232),(52.473,13.403)), # Grunewald / Tempelhofer Feld
])
def test_bundled_masks_cover_real_woodland_and_clear_land(key,wooded,open_point):
    theatre=THEATRES[key];terrain=theatre.terrain()
    def point(pair):return mapping.Point.from_latlng(mapping.LatLng(*pair),terrain)
    assert not geography.woodland_clear(point(wooded),theatre)
    assert geography.woodland_clear(point(open_point),theatre,footprint=220)
    info,mask,_=geography.woodland_data(key)
    manifest=json.loads((geography.DATA/'woodland.json').read_text())
    assert hashlib.sha256((geography.DATA/f'{key}-forest.png').read_bytes()).hexdigest()==info['mask_sha256']
    assert mask.mode=='1' and info['bounds']==list(theatre.bounds)
    assert len(manifest['sources'])==36 and manifest['license']=='CC BY 4.0'


def _small_mask(monkeypatch,*,margin=0):
    info={'bounds':[0,0,.02,.02],'step_degrees':.001}
    mask=Image.new('1',(20,20))
    monkeypatch.setattr(geography,'woodland_data',lambda key:(info,mask,margin))
    theatre=SimpleNamespace(key='sample')
    def point(lat=.01,lon=.01):return SimpleNamespace(latlng=lambda:SimpleNamespace(lat=lat,lng=lon))
    return mask,theatre,point


def test_complete_footprint_rejects_wooded_patch_between_centre_and_perimeter(monkeypatch):
    mask,theatre,point=_small_mask(monkeypatch)
    mask.putpixel((11,10),255)
    assert geography.woodland_clear(point(),theatre)
    assert not geography.woodland_clear(point(),theatre,footprint=300)
    assert not geography.suitable_ground(point(),theatre,footprint=300)


def test_clearance_margin_keeps_placements_back_from_the_tree_line(monkeypatch):
    mask,theatre,point=_small_mask(monkeypatch,margin=60)
    mask.putpixel((11,10),255)
    assert not geography.woodland_clear(point(.0093,.0107),theatre)


def test_woodland_data_edges_are_not_treated_as_clearings(monkeypatch):
    _,theatre,point=_small_mask(monkeypatch)
    assert not geography.woodland_clear(point(.025,.01),theatre)
    assert not geography.woodland_clear(point(.01,.0001),theatre,footprint=100)


def test_existing_manual_pin_is_preserved_and_woodland_override_is_explained():
    import random
    from ironanvil.model import resolve_aircraft
    theatre=THEATRES['caucasus'];terrain=theatre.terrain()
    options=MissionOptions(target_lat=42.1,target_lon=42.35,departure_airport='Batumi',seed=42)
    plan=geography.plan_scenario(options,theatre,terrain,resolve_aircraft(options.aircraft),random.Random(42))
    expected=mapping.Point.from_latlng(mapping.LatLng(42.1,42.35),terrain)
    assert plan.target.distance_to_point(expected)<.001
    assert any('woodland' in note and 'automatic' in note for note in plan.metadata['notes'])


def test_isolated_coastal_departure_uses_a_longer_clear_sortie_without_changing_airfield():
    import random
    from ironanvil.model import resolve_aircraft
    theatre=THEATRES['caucasus'];terrain=theatre.terrain()
    options=MissionOptions(departure_airport='Sochi-Adler',operation='rolling_thunder',
                           recovery='home_or_alternate',seed=178)
    plan=geography.plan_scenario(options,theatre,terrain,resolve_aircraft(options.aircraft),random.Random(178))
    assert plan.home.name=='Sochi-Adler'
    assert plan.home.position.distance_to_point(plan.target)>geography.distance_band(resolve_aircraft(options.aircraft),options.pace)[1]
    assert any('longer sortie' in note for note in plan.metadata['notes'])
    assert geography.woodland_clear(plan.target,theatre,footprint=220)
    assert all(geography.woodland_clear(p,theatre,footprint=170) for p in plan.sites.values())
    assert plan.ownership[plan.alternate.id]=='blue'


def test_genuinely_distant_alternate_still_has_a_briefing_warning():
    import random
    from ironanvil.model import resolve_aircraft
    theatre=THEATRES['caucasus'];terrain=theatre.terrain()
    options=MissionOptions(departure_airport='Sochi-Adler',target_lat=43.1,target_lon=40.8,
                           recovery='home_or_alternate',seed=178)
    plan=geography.plan_scenario(options,theatre,terrain,resolve_aircraft(options.aircraft),random.Random(178))
    assert plan.home.position.distance_to_point(plan.alternate.position)>120000
    assert any('longer friendly alternate' in note for note in plan.metadata['notes'])


@pytest.mark.parametrize('key',THEATRES)
@pytest.mark.parametrize('mission,operation',[
    ('facility','classic'),('facility','broken_relay'),('facility','supply_denial'),
    ('facility','rolling_thunder'),('line','classic'),('convoy','classic'),
    ('sead','classic'),('cap','classic'),
])
def test_automatic_enemy_ground_placements_are_outside_mapped_woodland(key,mission,operation):
    options=MissionOptions(map=key,mission=mission,operation=operation,seed=917,difficulty='hard')
    built,metadata=build_mission(options)
    theatre=THEATRES[key]
    country=built.country('Russia')
    for group in country.vehicle_group+country.static_group:
        for unit in group.units:
            assert geography.woodland_clear(unit.position,theatre),f'{key} {operation}/{mission}: {unit.name}'
    assert metadata['options']['target_lat'] is None
    for site in metadata['facility_sites']:
        point=mapping.Point(site['x'],site['z'],built.terrain)
        assert geography.woodland_clear(point,theatre,footprint=170)
