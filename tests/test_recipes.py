"""Replay settings are bounded plain data and never import another user's paths."""
from dataclasses import asdict,replace
import json
import zipfile

import pytest

from ironanvil.model import MissionOptions
from ironanvil.recipes import options_from_data,read_recipe,write_recipe
from ironanvil.generator import generate


def test_settings_roundtrip_keeps_gameplay_and_excludes_local_output(tmp_path):
    options=MissionOptions(operation='supply_denial',seed=342,pace='compact',enemy_response=False,
                          target_lat=42.1,target_lon=42.35,output_dir='Z:/Another Users Files')
    path=write_recipe(options,tmp_path/'share.json')
    assert read_recipe(path)==replace(options,output_dir=None)
    assert 'Z:/' not in path.read_text()


def test_replay_from_actual_mission_preserves_recipe(tmp_path):
    options=MissionOptions(operation='broken_relay',map='syria',seed=512,weather='rain',clients=4)
    path=generate(options,tmp_path/'actual.miz')
    assert read_recipe(path)==options
    with zipfile.ZipFile(path) as archive:
        assert archive.getinfo('KNEEBOARD/IMAGES/01-IronAnvil.png').file_size>10000
        html=archive.read('ironanvil-briefing.html').decode()
        assert 'Operation Broken Relay' in html and 'Replay seed: 512' in html
        assert 'data:image/png;base64,' in html and '<script' not in html


@pytest.mark.parametrize('data', [None,[],{}, {'options':[]}, {'options':{'mission':'not a mission'}},
    {'options':{'enemy_cap':'false'}}, {'options':{'line_units':'infantry'}},
    {'options':{'future_unsupported_option':True}}, {'options':{'mission':[]}}])
def test_bad_recipe_cannot_reach_generator(data):
    with pytest.raises(ValueError):options_from_data(data)


def test_archive_settings_size_is_bounded_before_reading(tmp_path):
    path=tmp_path/'oversized.miz'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('ironanvil.json',b' '*1100000)
    with pytest.raises(ValueError,match='large'):read_recipe(path)


def test_unrelated_and_invalid_files_are_helpful_errors(tmp_path):
    for name,content in [('not.json','{'),('not.miz','Not a zip')]:
        path=tmp_path/name;path.write_text(content)
        with pytest.raises(ValueError,match='Choose an Iron Anvil'):read_recipe(path)
