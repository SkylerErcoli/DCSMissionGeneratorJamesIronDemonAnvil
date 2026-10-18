"""Exercise the native launch code from saved missions without the controller."""
import os
import shutil
import subprocess
import zipfile

import pytest
from dcs import lua

from ironanvil.air_support import CAP_LAUNCH_FLAG
from ironanvil.generator import generate, PLAYER_GROUP
from ironanvil.model import MissionOptions


@pytest.mark.parametrize("map_key", ("caucasus", "syria", "germany"))
@pytest.mark.parametrize("start", ("cold", "air"))
def test_saved_native_cap_triggers_launch_from_second_client_without_runtime(map_key, start, tmp_path):
    executable = os.environ.get("LUA51") or shutil.which("lua5.1")
    if not executable:
        pytest.skip("Lua 5.1 required for saved-trigger execution")
    path = generate(MissionOptions(map=map_key, clients=2, difficulty="hard", start=start,
                                   operation="supply_denial", enemy_cap=True, seed=1964734450),
                    tmp_path / "native-cap.miz")
    with zipfile.ZipFile(path) as archive:
        saved = lua.loads(archive.read("mission").decode())["mission"]
    assert set(saved["trig"]["funcStartup"]) == {1}
    assert saved["trigrules"][1]["predicate"] == "triggerStart"
    clients = next(group for country in saved["coalition"]["blue"]["country"].values()
                   for group in country.get("plane", {}).get("group", {}).values()
                   if group["name"] == PLAYER_GROUP)
    enemy = [group for country in saved["coalition"]["red"]["country"].values()
             for group in country.get("plane", {}).get("group", {}).values()]
    assert len(enemy) == 2
    rules = {index: rule for index, rule in saved["trigrules"].items()
             if rule["comment"].startswith("Iron Anvil CAP launch - client ")}
    assert len(rules) == 2
    client_ids = {unit["unitId"] for unit in clients["units"].values()}
    group_ids = {group["groupId"] for group in enemy}
    for rule in rules.values():
        assert rule["predicate"] == "triggerOnce"
        assert rule["rules"][1] == {"predicate": "c_flag_is_false", "flag": CAP_LAUNCH_FLAG}
        assert rule["rules"][2]["unit"] in client_ids
        assert rule["rules"][2]["altitude"] == 30
        assert {a["group"] for a in rule["actions"].values() if a["predicate"] == "a_activate_group"} == group_ids
    data = {"conditions": {i: saved["trig"]["conditions"][i] for i in rules},
            "actions": {i: saved["trig"]["actions"][i] for i in rules},
            "client_ids": sorted(client_ids), "group_ids": sorted(group_ids)}
    script = tmp_path / "exercise-native.lua"
    script.write_text(lua.dumps(data, "DATA") + r'''
-- Deliberately no Iron Anvil runtime, event handler, Group or trigger.action.
Group=nil;trigger=nil
local flags,units,activated,fired={},{},{},{}
mission={trig={func={}}}
for _,id in ipairs(DATA.client_ids) do units[id]={active=false,agl=5000} end
function c_flag_is_false(flag) return not flags[flag] end
function c_unit_altitude_higher_AGL(id,height) return units[id].active and units[id].agl>height end
function a_activate_group(id) activated[id]=(activated[id] or 0)+1 end
function a_set_flag(flag) flags[flag]=true end
local conditions,actions={},{}
for index,code in pairs(DATA.conditions) do conditions[index]=assert(loadstring(code)) end
for index,code in pairs(DATA.actions) do actions[index]=assert(loadstring(code)) end
local function tick()
  for index,condition in pairs(conditions) do
    if not fired[index] and condition() then actions[index]();fired[index]=true end
  end
end
tick()
assert(next(activated)==nil,'unoccupied airborne slots must not launch CAP')
units[DATA.client_ids[1]]={active=true,agl=0}
tick()
assert(next(activated)==nil,'cold-start or taxiing pilots must not launch CAP')
units[DATA.client_ids[2]]={active=true,agl=40}
tick()
for _,id in ipairs(DATA.group_ids) do assert(activated[id]==1,'second client must launch every enemy group') end
units[DATA.client_ids[1]].agl=1000
tick();tick()
for _,id in ipairs(DATA.group_ids) do assert(activated[id]==1,'later departures must not relaunch or respawn CAP') end
print('PASS: saved native launch triggers')
''', encoding="utf-8")
    result = subprocess.run([executable, str(script)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: saved native launch triggers" in result.stdout


def test_cap_disabled_has_no_native_launch_rules_or_flights(tmp_path):
    path = generate(MissionOptions(enemy_cap=False, seed=1964734450), tmp_path / "no-cap.miz")
    with zipfile.ZipFile(path) as archive:
        saved = lua.loads(archive.read("mission").decode())["mission"]
    assert not any(rule["comment"].startswith("Iron Anvil CAP launch") for rule in saved["trigrules"].values())
    assert not any(country.get("plane", {}).get("group") for country in saved["coalition"]["red"]["country"].values())
