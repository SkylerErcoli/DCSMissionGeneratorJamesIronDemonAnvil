#!/usr/bin/env python3
"""Build small offline tree-cover masks; requires requirements-data.txt only.

Read overviews of immutable ESA WorldCover 2021 v200 COGs over HTTP ranges.
Cache categorical samples, hash their raw pixels, and retain source/transform
metadata. This does not download whole DCS maps or add a runtime dependency.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ironanvil.theatres import THEATRES

OUT = ROOT / "ironanvil/assets/geography"
CACHE = Path(os.environ.get("IRONANVIL_GEOGRAPHY_CACHE", ROOT.parent / ".cache/ironanvil/geography-source"))
MANIFEST = OUT / "woodland.json"
STEP = .001  # 111 m north/south; roughly 62–96 m east/west on these maps.
SIDE = 3000
BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"


def tile_name(south, west):
    return f"N{south:02d}E{west:03d}"


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    sources = old.get("sources", {})
    jobs = sorted({(lat, lon) for theatre in THEATRES.values()
                   for lat in range(math.floor(theatre.bounds[1]/3)*3, math.ceil(theatre.bounds[3]/3)*3, 3)
                   for lon in range(math.floor(theatre.bounds[0]/3)*3, math.ceil(theatre.bounds[2]/3)*3, 3)})

    def sample(job):
        south, west = job
        name = tile_name(south, west)
        url = BASE + f"ESA_WorldCover_10m_2021_v200_{name}_Map.tif"
        cache = CACHE / f"worldcover-v200-{name}-step001.png"
        if cache.exists():
            with Image.open(cache) as image:
                pixels = np.array(image)
        else:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                              CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_TIMEOUT=30,
                              GDAL_HTTP_MAX_RETRY=2, GDAL_CACHEMAX=64*1024*1024):
                with rasterio.open(url) as dataset:
                    if tuple(dataset.bounds) != (west, south, west+3, south+3):
                        raise ValueError("Unexpected source georeferencing: " + url)
                    pixels = dataset.read(1, out_shape=(SIDE, SIDE), resampling=Resampling.nearest)
            Image.fromarray(pixels).save(cache, optimize=True)
        if pixels.shape != (SIDE, SIDE) or pixels.dtype != np.uint8:
            raise ValueError("Invalid cached woodland sample: " + name)
        digest = hashlib.sha256(pixels.tobytes()).hexdigest()
        if url in sources and sources[url]["sample_sha256"] != digest:
            raise ValueError("Sample changed; review upstream data/cache: " + url)
        print(name, "sample verified", flush=True)
        return job, pixels, url, {"sample_sha256": digest, "sample_shape": [SIDE, SIDE]}

    masks = {}
    maps = {}
    for key, theatre in THEATRES.items():
        west, south, east, north = theatre.bounds
        width, height = round((east-west)/STEP), round((north-south)/STEP)
        # Unknown/uncovered data is blocked, not silently treated as a clearing.
        masks[key] = Image.new("1", (width, height), 1)
        maps[key] = {"bounds": list(theatre.bounds), "step_degrees": STEP, "size": [width, height]}
    manifest_sources = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (lat, lon), pixels, url, record in pool.map(sample, jobs):
            manifest_sources[url] = record
            for key, theatre in THEATRES.items():
                w, s, e, n = theatre.bounds
                left, bottom, right, top = max(w,lon), max(s,lat), min(e,lon+3), min(n,lat+3)
                if right <= left or top <= bottom:
                    continue
                x, y = round((left-w)/STEP), round((n-top)/STEP)
                sx, sy = round((left-lon)/STEP), round((lat+3-top)/STEP)
                width, height = round((right-left)/STEP), round((top-bottom)/STEP)
                region = pixels[sy:sy+height, sx:sx+width]
                blocked = ((region == 10) | (region == 0)).astype("uint8") * 255
                masks[key].paste(Image.fromarray(blocked).convert("1"), (x,y))
    for key, image in masks.items():
        path = OUT / f"{key}-forest.png"
        image.save(path, optimize=True)
        maps[key]["mask_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(key, image.size, path.stat().st_size, "bytes", flush=True)
    manifest = {"format": 1, "source": "ESA WorldCover 2021 v200, tree-cover class 10",
                "citation": "Zanaga et al. (2022), ESA WorldCover 10 m 2021 v200, doi:10.5281/zenodo.7254221",
                "license": "CC BY 4.0", "source_url": "https://esa-worldcover.org/en/data-access",
                "sampling": "Nearest categorical overview samples on a 0.001-degree grid; not native 10 m detail.",
                "clearance_m": 60, "nodata": "Uncovered/zero-valued samples are blocked.",
                "note": "Approximate real-world tree cover; does not certify DCS tree placement, especially historical terrain.",
                "maps": maps, "sources": manifest_sources}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
