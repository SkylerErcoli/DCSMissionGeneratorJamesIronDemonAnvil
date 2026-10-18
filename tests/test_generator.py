"""Regression checks on actual mission objects and serialized .miz contents."""
import itertools
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dcs import Mission, lua, planes
from ironanvil.generator import build_mission, generate, PLAYER_GROUP
from ironanvil.mapdata import is_land
from ironanvil.model import MissionOptions


MAPS = ("caucasus", "syria", "germany")
MISSIONS = ("facility", "line", "convoy", "sead", "cap")
AD_TYPES = {"Osa 9A33 ln", "Kub 1S91 str", "Kub 2P25 ln", "SA-18 Igla manpad",
            "ZSU-23-4 Shilka", "Ural-375 ZU-23", "Ural-375 ZU-23 Insurgent", "Igla manpad INS"}


class GeneratorTests(unittest.TestCase):
    def test_global_toggles_are_independent_for_every_mission(self):
        for mission_type, cap, defenses in itertools.product(MISSIONS, (False, True), (False, True)):
            with self.subTest(mission=mission_type, cap=cap, air_defenses=defenses):
                mission, metadata = build_mission(MissionOptions(
                    mission=mission_type, enemy_cap=cap, air_defenses=defenses,
                    line_units=("infantry", "manpads", "aaa")))
                red = mission.country("Russia")
                self.assertEqual(bool(red.plane_group), cap)
                self.assertEqual(bool(metadata["runtime"]["cap_groups"]), cap)
                types = {unit.type for group in red.vehicle_group for unit in group.units}
                self.assertEqual(bool(types & AD_TYPES), defenses)
                if mission_type == "sead":
                    self.assertTrue(metadata["runtime"]["target_groups"])
                    if not defenses:
                        self.assertIn("OBJECTIVE AIR DEFENSE SUPPORT", metadata["runtime"]["target_groups"])

    def test_every_map_and_start_has_blue_airport_and_supplies_in_saved_mission(self):
        with tempfile.TemporaryDirectory() as directory:
            for terrain, start, clients in itertools.product(MAPS, ("cold", "hot", "runway", "air"), (1, 4)):
                with self.subTest(map=terrain, start=start, clients=clients):
                    path = generate(MissionOptions(map=terrain, start=start, clients=clients,
                                    enemy_cap=False, air_defenses=False), Path(directory) / "check.miz")
                    with zipfile.ZipFile(path) as archive:
                        metadata = json.loads(archive.read("ironanvil.json"))
                        warehouses = lua.loads(archive.read("warehouses").decode())["warehouses"]
                        airport = warehouses["airports"][metadata["home_airport_id"]]
                        self.assertEqual(airport["coalition"], "BLUE")
                        self.assertTrue(airport["unlimitedFuel"])
                        self.assertTrue(airport["unlimitedMunitions"])
                        self.assertEqual(archive.testzip(), None)
                        script = archive.read("l10n/DEFAULT/ironanvil_runtime.lua").decode()
                        self.assertRegex(script, r"^IRON_ANVIL\s*=")
                        self.assertIn("IRON_ANVIL_MISSION_COMPLETE", script)
                        self.assertNotIn("a_do_script(", archive.read("mission").decode())
                    reloaded = Mission()
                    reloaded.load_file(str(path))
                    group = next(g for g in reloaded.country("USA").plane_group if g.name == PLAYER_GROUP)
                    self.assertEqual(len(group.units), clients)
                    self.assertTrue(all(unit.skill.value == "Client" for unit in group.units))
                    expected_action = {"cold": "From Parking Area", "hot": "From Parking Area Hot",
                                       "runway": "From Runway", "air": "Turning Point"}[start]
                    self.assertEqual(group.points[0].action.value, expected_action)
                    self.assertTrue(reloaded.terrain.airport_by_id(metadata["home_airport_id"]).is_blue())

    def test_fortifications_are_sandbags_and_positions_are_staggered(self):
        mission, metadata = build_mission(MissionOptions(mission="line", seed=24, air_defenses=False))
        red = mission.country("Russia")
        cover = [u for g in red.static_group if g.name.startswith("Line sandbags") for u in g.units]
        self.assertGreaterEqual(len(cover), 18)
        self.assertTrue(all(u.type.startswith("Sandbag_") for u in cover))
        line = [g for g in red.vehicle_group if g.name.startswith("LINE ")]
        self.assertTrue(all(g.name in metadata["runtime"]["target_groups"] for g in line))
        points = [g.units[0].position for g in line]
        # A straight line has near-zero signed perpendicular distances.
        origin, end = points[0], points[-1]
        length = origin.distance_to_point(end)
        distances = [abs((end.x-origin.x)*(p.y-origin.y) - (end.y-origin.y)*(p.x-origin.x))/length for p in points[1:-1]]
        self.assertGreater(max(distances), 20)

    def test_hornet_has_legal_targeting_pod_for_every_ground_mission(self):
        expected = planes.FA_18C_hornet.Pylon4.AN_ASQ_228_ATFLIR___Targeting_Pod[1]["clsid"]
        for mission_type in ("facility", "line", "convoy", "sead"):
            with self.subTest(mission=mission_type):
                mission, _ = build_mission(MissionOptions(mission=mission_type))
                for unit in mission.country("USA").plane_group[0].units:
                    self.assertEqual(unit.pylons[4]["CLSID"], expected)
                    self.assertIn(5, unit.pylons)

    def test_facility_compounds_have_four_sides_a_gate_and_varied_seeded_styles(self):
        styles = set()
        for seed in range(8):
            mission, metadata = build_mission(MissionOptions(seed=seed, air_defenses=False, enemy_cap=False))
            same_mission, same_metadata = build_mission(MissionOptions(seed=seed, air_defenses=False, enemy_cap=False))
            self.assertEqual(metadata["compound_style"], same_metadata["compound_style"])
            styles.add(metadata["compound_style"])
            groups = mission.country("Russia").static_group
            perimeter = [g.units[0] for g in groups if g.name.startswith("Compound perimeter")]
            self.assertTrue(all(unit.type == "Container_40ft" for unit in perimeter))
            objectives = [g.units[0].position for g in groups if g.name.startswith("OBJECTIVE ")]
            left, right = min(u.position.x for u in perimeter), max(u.position.x for u in perimeter)
            bottom, top = min(u.position.y for u in perimeter), max(u.position.y for u in perimeter)
            for point in objectives:
                self.assertTrue(left < point.x < right and bottom < point.y < top)
            for side in (-1, 1):
                self.assertGreater(len([g for g in groups if g.name.startswith(f"Compound perimeter horizontal {side}")]), 10)
                self.assertGreater(len([g for g in groups if g.name.startswith(f"Compound perimeter vertical {side}")]), 10)
            upper = [u for u in perimeter if abs(u.position.y - top) < .01]
            lower = [u for u in perimeter if abs(u.position.y - bottom) < .01]
            self.assertEqual(len(upper), len(lower) + 1)  # One entrance section is omitted.
        self.assertEqual(styles, {"container yard", "long depot", "divided compound"})

    def test_all_maps_missions_have_ground_targets_on_land(self):
        for terrain, mission_type in itertools.product(MAPS, MISSIONS):
            with self.subTest(map=terrain, mission=mission_type):
                mission, _ = build_mission(MissionOptions(map=terrain, mission=mission_type))
                for country in (mission.country("USA"), mission.country("Russia")):
                    for group in country.vehicle_group + country.static_group:
                        for unit in group.units:
                            coords = unit.position.latlng()
                            self.assertTrue(is_land(coords.lat, coords.lng), (group.name, coords))

    def test_seed_is_repeatable_and_does_not_change_callers_random_state(self):
        with tempfile.TemporaryDirectory() as directory:
            before = random.getstate()
            first = generate(MissionOptions(seed=981), Path(directory) / "first.miz")
            self.assertEqual(random.getstate(), before)
            second = generate(MissionOptions(seed=981), Path(directory) / "second.miz")
            with zipfile.ZipFile(first) as a, zipfile.ZipFile(second) as b:
                for member in ("mission", "warehouses", "ironanvil.json", "l10n/DEFAULT/ironanvil_runtime.lua"):
                    self.assertEqual(a.read(member), b.read(member))

    def test_failed_write_preserves_existing_mission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.miz"
            path.write_bytes(b"original mission")
            with patch.object(Mission, "save", side_effect=OSError("simulated disk failure")):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    generate(MissionOptions(), path)
            self.assertEqual(path.read_bytes(), b"original mission")


if __name__ == "__main__":
    unittest.main()
