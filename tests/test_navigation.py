"""Navigation uses public intelligence and matches the actual departure catalogue."""
from io import BytesIO
from html import unescape
import json
import zipfile

from PIL import Image
import pytest

from ironanvil.generator import generate, PLAYER_GROUP
from ironanvil.model import MissionOptions
from ironanvil.navigation import coordinate_formats
from ironanvil.theatres import get_theatre
from dcs import lua


@pytest.mark.parametrize('lat,lon,ddm,dms',[
    (42.25,43.125,"N42 15.000' E043 07.500'",'N42 15\' 00.0" E043 07\' 30.0"'),
    (-12.9999999,-179.9999999,"S13 00.000' W180 00.000'",'S13 00\' 00.0" W180 00\' 00.0"'),
    (0,0,"N00 00.000' E000 00.000'",'N00 00\' 00.0" E000 00\' 00.0"'),
])
def test_cockpit_formats_handle_hemispheres_and_carry(lat,lon,ddm,dms):
    formats=coordinate_formats(lat,lon)
    assert formats['ddm']==ddm and formats['dms']==dms


@pytest.mark.parametrize('lat,lon',[(float('nan'),20),(30,float('inf')),(91,20),(20,-181)])
def test_invalid_coordinate_values_are_rejected(lat,lon):
    with pytest.raises(ValueError):coordinate_formats(lat,lon)


@pytest.mark.parametrize('map,departure',[
    ('caucasus','Sochi-Adler'),('syria','Damascus'),('germany','Stendal'),
])
@pytest.mark.parametrize('intel',['precise','search'])
def test_saved_navigation_card_uses_public_points_and_real_airport_radios(tmp_path,map,departure,intel):
    path=generate(MissionOptions(map=map,departure_airport=departure,operation='rolling_thunder',
        intelligence=intel,recovery='home_or_alternate',tanker=True,awacs=True,seed=178),tmp_path/'navigation.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        html=unescape(archive.read('ironanvil-briefing.html').decode())
        with Image.open(BytesIO(archive.read('KNEEBOARD/IMAGES/02-Navigation.png'))) as image:
            assert image.size==(1000,1440);image.verify()
        mission=lua.loads(archive.read('mission').decode())['mission']
    nav=metadata['navigation']
    if departure=='Sochi-Adler':
        assert any('longer friendly alternate' in note for note in metadata['geography']['notes'])
        assert any('longer friendly alternate' in line for line in metadata['runtime']['briefing_lines'])
    assert len(nav['points'])==len(metadata['planner']['points'])
    for actual,public in zip(nav['points'],metadata['planner']['points']):
        assert actual['label']==public['label'] and actual['role']==public['role']
        assert actual['coordinates']==coordinate_formats(public['lat'],public['lon'])
        assert actual['coordinates']['ddm'] in html
    if intel=='search':
        assert {point['role'] for point in nav['points']}=={'home','alternate','search'}
        private=coordinate_formats(metadata['target_lat'],metadata['target_lon'])
        assert all(value not in html for value in private.values())
    terrain=get_theatre(map).terrain()
    for base in nav['airports']:
        airport=terrain.airports[base['name']]
        assert base['runways']==[runway.name for runway in airport.runways]
        assert f'VHF AM {airport.atc_radio.vhf_high_hz/1_000_000:.3f} MHz' in base['radios']
    # New-install/recommended cold starts must reach the actual DCS route.
    group=next(group for country in mission['coalition']['blue']['country'].values()
        for group in country.get('plane',{}).get('group',{}).values() if group['name']==PLAYER_GROUP)
    first=group['route']['points'][1]
    assert first['type']=='TakeOffParking' and first['action']=='From Parking Area'


def test_helipad_card_does_not_invent_a_runway(tmp_path):
    path=generate(MissionOptions(map='syria',aircraft='AH_64D_BLK_II',departure_airport='Naqoura',
        operation='broken_relay',seed=42),tmp_path/'helipad.miz')
    with zipfile.ZipFile(path) as archive:metadata=json.loads(archive.read('ironanvil.json'))
    assert metadata['navigation']['airports'][0]['runways']==[]
