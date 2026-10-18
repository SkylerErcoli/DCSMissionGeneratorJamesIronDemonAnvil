"""Search-mode public briefings and flight plans must not expose exact objectives."""
from io import BytesIO
import json
import zipfile

from PIL import Image
from dcs import Mission,lua
import pytest

from ironanvil.generator import generate
from ironanvil.model import MissionOptions


@pytest.mark.parametrize('terrain',['caucasus','syria','germany'])
@pytest.mark.parametrize('operation',['broken_relay','rolling_thunder'])
def test_search_mode_withholds_locations_and_uses_a_real_search_waypoint(tmp_path,terrain,operation):
    path=generate(MissionOptions(map=terrain,operation=operation,intelligence='search',seed=178,
        recovery='home_or_alternate',tanker=True,awacs=True),tmp_path/'search.miz')
    with zipfile.ZipFile(path) as archive:
        metadata=json.loads(archive.read('ironanvil.json'))
        html=archive.read('ironanvil-briefing.html').decode()
        dictionary=archive.read('l10n/DEFAULT/dictionary').decode()
        actual=f"{metadata['target_lat']:.5f}, {metadata['target_lon']:.5f}"
        assert actual not in html and actual not in dictionary
        for site in metadata['facility_sites']:
            assert f"{site['latitude']:.5f}, {site['longitude']:.5f}" not in html
        saved=lua.loads(archive.read('mission').decode())['mission']
        for country in saved['coalition']['red']['country'].values():
            for category in ('vehicle','static'):
                for group in country.get(category,{}).get('group',{}).values():
                    assert group['hidden'] is True
        with Image.open(BytesIO(archive.read('KNEEBOARD/IMAGES/01-IronAnvil.png'))) as image:
            image.verify()
    intelligence=metadata['runtime']['intelligence']
    assert intelligence['required_seconds']==45 and intelligence['radius']>1000
    assert intelligence['center']!=metadata['runtime']['target']
    roles={point['role'] for point in metadata['planner']['points']}
    assert roles=={'home','alternate','search'}
    mission=Mission();mission.load_file(str(path))
    group=mission.coalition['blue'].find_group('IRON ANVIL CLIENTS')
    search=next(point for point in group.points if point.name=='SEARCH AREA')
    assert search.position.x==pytest.approx(intelligence['center']['x'])
    assert search.position.y==pytest.approx(intelligence['center']['z'])
    assert not any(point.name=='BONUS - OPTIONAL' for point in group.points)


def test_ground_search_mode_is_optional_and_cap_rejects_it():
    assert MissionOptions(intelligence='precise').validate()
    with pytest.raises(ValueError,match='ground missions'):MissionOptions(mission='cap',intelligence='search').validate()
    with pytest.raises(ValueError):MissionOptions(intelligence='unknown').validate()
