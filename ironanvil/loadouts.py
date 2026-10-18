"""Payloads made exclusively from the selected aircraft's supported pylons.

The Hornet has a curated payload. Other modules use a conservative heuristic;
the DCS rearm menu remains the authoritative place to tune those payloads.
"""
from __future__ import annotations


def pylon_choices(aircraft):
    result = {}
    for number in sorted(getattr(aircraft, "pylons", ())):
        pylon = getattr(aircraft, f"Pylon{number}", None)
        result[number] = [
            (name, value) for name, value in vars(pylon).items()
            if isinstance(value, tuple) and len(value) == 2
            and isinstance(value[1], dict) and value[1].get("clsid")
        ] if pylon else []
    return result


def _choose(choices, words):
    for word in words:
        matching = [(name, weapon) for name, weapon in choices if word in name.lower()]
        if matching:
            # Prefer single weapons to large multiple ejector racks.
            return min(matching, key=lambda item: ("2_x" in item[0] or "3_x" in item[0], len(item[0])))[1]
    return None


def apply_loadout(group, mission_type: str, mode: str = "auto") -> None:
    aircraft = group.units[0].unit_type
    if mode == "default":
        # This may return no weapons when no local DCS payloads are installed.
        from dcs import task
        main = {"cap": task.CAP, "sead": task.SEAD}.get(mission_type, task.GroundAttack)
        group.load_task_default_loadout(main)
        return
    choices = pylon_choices(aircraft)
    selected = {}
    if aircraft.__name__ == "FA_18C_hornet":
        for number in (1, 9):
            selected[number] = _choose(choices[number], ["aim_9x"])
        selected[5] = _choose(choices[5], ["fuel_tank"])
        selected[6] = _choose(choices[6], ["aim_120c"])
        if mission_type == "cap":
            for number in (2, 3, 4, 7, 8):
                selected[number] = _choose(choices[number], ["aim_120c"])
        else:
            # The cheek station leaves the centreline tank and weapon stations free.
            selected[4] = _choose(choices[4], ["atflir", "litening"])
            for number in (2, 3, 7, 8):
                selected[number] = _choose(choices[number],
                    ["agm_88"] if mission_type == "sead" else ["gbu_38", "gbu_12", "mk_82"])
    else:
        available = set(choices)
        if mission_type != "cap":
            for number in sorted(available):
                pod = _choose(choices[number], ["atflir", "litening", "sniper", "targeting_pod", "tgp"])
                if pod:
                    selected[number] = pod
                    available.remove(number)
                    break
        # Reserve opposite compatible stations for self defence on ground sorties.
        # CAP instead prefers radar missiles on every compatible station below.
        if mission_type != "cap":
            missiles = {number: _choose(choices[number], ["aim_9x", "aim_9m", "r_73", "r_60", "magic_2", "aim_9", "ir_aam"])
                        for number in sorted(available)}
            compatible = [number for number, weapon in missiles.items() if weapon]
            if compatible:
                for number in {compatible[0], compatible[-1]}:
                    selected[number] = missiles[number]
                    available.remove(number)
        if mission_type == "cap":
            priorities = ["aim_120", "r_77", "r_27", "aim_7", "super_530", "aim_9", "r_73", "r_60"]
        elif mission_type == "sead":
            priorities = ["agm_88", "kh_58", "kh_25mp", "kh_31p", "agm_122", "agm_65", "gbu_12", "mk_82", "fab_250"]
        else:
            priorities = ["agm_65", "agm_114", "vikhr", "gbu_12", "gbu_38", "gbu_49", "kh_25ml", "mk_82", "fab_250", "hydra", "lau_68", "s_8", "s_5", "hvar", "an_m64"]
        tank_loaded = False
        for number in sorted(available):
            tank = _choose(choices[number], ["fuel_tank", "droptank", "external_tank"])
            weapon = _choose(choices[number], priorities)
            if weapon:
                selected[number] = weapon
            elif tank and not tank_loaded:
                selected[number] = tank
                tank_loaded = True
    for unit in group.units:
        unit.pylons.clear()
        for weapon in selected.values():
            if weapon:
                unit.load_pylon(weapon)


def tanker_type(aircraft):
    """Return a compatible tanker where the module exposes a refuelling system."""
    from dcs import planes
    identifier = aircraft.__name__.lower()
    if getattr(aircraft, "helicopter", False):
        return None
    if any(identifier.startswith(prefix) for prefix in ("su_", "mig_29", "mig_31", "tu_")):
        return getattr(planes, "IL_78M", None)
    if identifier.startswith("av8") or identifier.startswith("av_8"):
        return getattr(planes, "KC130", None)
    if any(identifier.startswith(prefix) for prefix in ("fa_18", "f_a_18", "f_14", "m_2000", "mirage", "jf_17", "rafale")):
        return getattr(planes, "KC135MPRS", None)
    if any(identifier.startswith(prefix) for prefix in ("f_16", "f_15", "a_10", "f_4")):
        return getattr(planes, "KC_135", None)
    return None


def payload_summary(group, mode):
    """Report actual serialized stations; do not infer that a local preset is armed."""
    unit=group.units[0]
    choices=pylon_choices(unit.unit_type)
    stores=[]
    for station,loaded in sorted(unit.pylons.items()):
        clsid=loaded.get('CLSID')
        match=next(((name,value[1]) for name,value in choices.get(station,[]) if value[1]['clsid']==clsid),None)
        name=(match[1].get('name') or match[0].replace('_',' ')) if match else str(clsid)
        stores.append({'station':station,'name':name,'clsid':clsid})
    return {'mode':mode,'stores':stores,'station_count':len(stores),
            'warning':None if stores else 'No external stores were loaded. Check weapons in DCS before flying.'}


def payload_text(summary):
    from collections import Counter
    if summary.get('warning'):return summary['warning']
    counts=Counter(store['name'] for store in summary.get('stores',[]))
    return 'Stores: '+', '.join(f'{count} x {name}' for name,count in counts.items())
