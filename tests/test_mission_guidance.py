"""Briefings describe real objectives and stores without exposing search locations."""
import json
import zipfile
from dcs import lua
import pytest
from ironanvil.generator import generate, PLAYER_GROUP
from ironanvil.model import MissionOptions


@pytest.mark.parametrize('options',[
    MissionOptions(map='caucasus',mission='sead',seed=42),
    MissionOptions(map='syria',mission='cap',enemy_cap=False,seed=42),
    MissionOptions(map='germany',operation='rolling_thunder',intelligence='search',seed=178),
    MissionOptions(aircraft='AH_64D_BLK_II',operation='broken_relay',start='air',seed=42),
])
def test_help_and_store_manifest_match_the_actual_saved_mission(tmp_path,options):
    path=generate(options,tmp_path/'guidance.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        saved=lua.loads(archive.read('mission').decode())['mission']
        html=archive.read('ironanvil-briefing.html').decode()
    help_text='\n'.join(metadata['runtime']['briefing_lines'])
    assert 'RECOVERY: land every surviving' in help_text and '251 MHz' in help_text
    assert 'Your job' in html and '<details>' in html
    clients=next(group for country in saved['coalition']['blue']['country'].values()
        for category in ('plane','helicopter') for group in country.get(category,{}).get('group',{}).values()
        if group['name']==PLAYER_GROUP)
    expected={store['station']:store['clsid'] for store in metadata['loadout']['stores']}
    assert expected
    for unit in clients['units'].values():
        actual={number:store['CLSID'] for number,store in unit['payload']['pylons'].items()}
        assert actual==expected
    if options.intelligence=='search':
        assert f"{metadata['target_lat']:.5f}, {metadata['target_lon']:.5f}" not in help_text
        assert '45 continuous seconds' in help_text
    if options.mission=='cap':assert 'five minutes' in help_text and 'No enemy fighters' in help_text
    if options.operation!='classic':assert 'REQUIRED: Disable 2' in help_text and 'OPTIONAL:' in help_text


def test_missing_local_payload_is_reported_in_help_and_browser_briefing(tmp_path,monkeypatch):
    from dcs.unitgroup import FlyingGroup
    monkeypatch.setattr(FlyingGroup,'load_task_default_loadout',lambda *args:None)
    path=generate(MissionOptions(loadout='default'),tmp_path/'empty-local-preset.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        html=archive.read('ironanvil-briefing.html').decode()
    assert metadata['loadout']['stores']==[] and metadata['loadout']['station_count']==0
    assert 'No external stores were loaded' in metadata['loadout']['warning']
    assert metadata['loadout']['warning'] in html and metadata['loadout']['warning'] in metadata['runtime']['briefing_lines']
