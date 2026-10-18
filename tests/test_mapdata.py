"""Map geometry and actual offline image/cache behavior, independent of a display."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from ironanvil.mapdata import (Chart, ChartStore, TileCache, Viewport, is_land,
                              latlon_to_world, validate_bounds, world_to_latlon)


class MapGeometryTests(unittest.TestCase):
    def test_geographic_mercator_round_trip(self):
        for lat, lon in ((0, 0), (42.1, 42.35), (35.2, 37), (52.55, 11.4), (-80, -170)):
            restored = world_to_latlon(*latlon_to_world(lat, lon))
            self.assertAlmostEqual(restored[0], lat, places=9)
            self.assertAlmostEqual(restored[1], lon, places=9)
        self.assertEqual(latlon_to_world(0, 0), (.5, .5))

    def test_click_after_zoom_and_pan_keeps_geographic_position(self):
        viewport = Viewport(width=700, height=450)
        viewport.fit((36, 40, 46, 46))
        before = viewport.to_latlon(137, 208)
        viewport.zoom_at(2, 137, 208)
        after = viewport.to_latlon(137, 208)
        self.assertAlmostEqual(after[0], before[0])
        self.assertAlmostEqual(after[1], before[1])
        viewport.center_x += .002
        viewport.center_y -= .001
        target = (42.1, 42.35)
        restored = viewport.to_latlon(*viewport.to_pixel(*target))
        self.assertAlmostEqual(restored[0], target[0])
        self.assertAlmostEqual(restored[1], target[1])

    def test_fit_contains_all_theatre_corners(self):
        for bounds in ((36, 40, 46, 46), (32, 31, 42, 38), (7, 49, 17, 55.5)):
            view = Viewport(width=800, height=450)
            view.fit(bounds)
            west, south, east, north = bounds
            for lat, lon in ((south, west), (north, east)):
                x, y = view.to_pixel(lat, lon)
                self.assertGreaterEqual(x, 0)
                self.assertLessEqual(x, view.width)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(y, view.height)

    def test_invalid_bounds_do_not_silently_reverse_or_accept_nan(self):
        for bounds in ((10, 40, 5, 45), (10, 50, 12, 40), (0, -90, 1, 90), (0, 1, math.nan, 5), (1, 2, 3)):
            with self.assertRaises(ValueError):
                validate_bounds(bounds)

    def test_real_geographic_land_and_sea_samples(self):
        for point in ((42.1, 42.35), (35.2, 37), (52.55, 11.4), (52.52, 13.4), (35,34)):
            self.assertTrue(is_land(*point), point)
        # 35 N, 34 E is inland near Ayia Napa; the old coarse mask missed it.
        for point in ((43, 36), (34, 33), (34.85, 34.2), (55, 7)):
            self.assertFalse(is_land(*point), point)


class OfflineChartTests(unittest.TestCase):
    def test_import_round_trip_preserves_pixels_bounds_and_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "dcs-chart.png"
            original = Image.new("RGB", (64, 32), (130, 60, 45))
            original.putpixel((10, 20), (1, 2, 3))
            original.save(source)
            Path(str(source) + ".json").write_text(json.dumps({
                "bounds": [7, 49, 17, 55.5], "crs": "EPSG:3857"}), encoding="utf-8")
            store = ChartStore(root / "cache")
            stored = store.save("germany", ChartStore.metadata(source))
            source.unlink()  # Reopening must use the persistent local copy.
            restored = store.load("germany")
            self.assertEqual(restored.bounds, (7., 49., 17., 55.5))
            self.assertEqual(restored.crs, "EPSG:3857")
            self.assertEqual(restored.path, stored.path)
            with Image.open(restored.path) as result:
                self.assertEqual(result.getpixel((10, 20)), (1, 2, 3))
            store.clear("germany")
            self.assertIsNone(store.load("germany"))

    def test_geographic_and_mercator_charts_have_correct_geographic_anchors(self):
        for crs in ("EPSG:4326", "EPSG:3857"):
            chart = Chart(Path("map.png"), (7, 49, 17, 55.5), crs)
            self.assertEqual(chart.source_pixel(55.5, 7, (100, 100)), (0, 0))
            x, y = chart.source_pixel(49, 17, (100, 100))
            self.assertAlmostEqual(x, 100)
            self.assertAlmostEqual(y, 100)
        geographic = Chart(Path("map.png"), (0, 10, 10, 70), "EPSG:4326")
        mercator = Chart(Path("map.png"), (0, 10, 10, 70), "EPSG:3857")
        self.assertEqual(geographic.source_pixel(40, 5, (100, 100)), (50, 50))
        self.assertNotAlmostEqual(mercator.source_pixel(40, 5, (100, 100))[1], 50)

    def test_unknown_projection_and_path_traversal_are_rejected(self):
        with self.assertRaises(ValueError):
            Chart(Path("map.png"), (7, 49, 17, 55.5), "DCS screenshot")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                ChartStore(directory).load("../../somewhere")

    def test_offline_tile_cache_uses_real_saved_png_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "6" / "35" / "20.png"
            path.parent.mkdir(parents=True)
            Image.new("RGB", (256, 256), (12, 45, 78)).save(path)
            cache = TileCache(directory)
            tile = cache.get(6, 35, 20, online=False)
            self.assertEqual(tile.getpixel((0, 0)), (12, 45, 78))
            self.assertIsNone(cache.get(6, 36, 20, online=False))
            with self.assertRaises(ValueError):
                cache.get(6, 64, 20)


if __name__ == "__main__":
    unittest.main()
