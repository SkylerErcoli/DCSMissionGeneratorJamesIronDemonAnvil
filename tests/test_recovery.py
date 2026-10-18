"""Approved alternates must actually be friendly and supplied in the saved mission."""
import json
import zipfile
from dcs import Mission,lua
import pytest
from ironanvil.generator import generate
from ironanvil.model import MissionOptions


@pytest.mark.parametrize('terrain',['caucasus','syria','germany'])
@pytest.mark.parametrize('aircraft',['FA_18C_hornet','AH_64D_BLK_II'])
def test_saved_alternate_is_supplied_compatible_and_distinct(tmp_path,terrain,aircraft):
    path=generate(MissionOptions(map=terrain,aircraft=aircraft,operation='broken_relay',
        recovery='home_or_alternate',start='air'),tmp_path/'recovery.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        warehouses=lua.loads(archive.read('warehouses').decode())['warehouses']
        html=archive.read('ironanvil-briefing.html').decode()
        assert metadata['alternate_airport'] in html and 'withdrawal' in html
    mission=Mission();mission.load_file(str(path))
    bases=metadata['runtime']['recovery_bases']
    assert len(bases)==2 and bases[0]['name']!=bases[1]['name']
    for base in bases:
        airport=next(a for a in mission.terrain.airports.values() if a.name==base['name'])
        assert airport.is_blue()
        assert warehouses['airports'][airport.id]['unlimitedFuel']
        assert warehouses['airports'][airport.id]['unlimitedMunitions']
        if aircraft=='FA_18C_hornet':assert airport.runways
    assert metadata['runtime']['allow_withdrawal'] is True


def test_recovery_input_rejects_unknown_values():
    with pytest.raises(ValueError):MissionOptions(recovery='any_enemy_base').validate()
    with pytest.raises(ValueError):MissionOptions(allow_withdrawal='yes').validate()
