# Procedural mission geography

Every classic mission and cooperative operation now uses the same seeded planning stage. The planner balances geographic cells before selecting a compatible departure, then samples full-circle eligible headings and a distance band around Close / Standard / Longer. It does not select from a catalogue of complete missions.

The selected scenario still determines its job: Broken Relay is a fuel strike; Facility strike can choose fuel, command, ammunition, factory or radar sites. A seed repeats the procedural choices in the same version. Changing generator algorithms can change an old seed's layout; the saved `.miz` remains the exact replay.

## What constrains placement

- Aircraft/runway compatibility and enough parking for all cold-start clients.
- Supported planner bounds, detailed public coastlines/lakes and a clear ground footprint.
- Approximate public elevation: reject high or steep footprints rather than dropping compounds onto mountain ridges.
- Separation from airfield centers; room for related operation sites before accepting the main target.
- Convoys start near approximate main-road corridors. Destinations and response staging seek the same corridors; native DCS APIs choose actual routes after takeoff/dispatch. A native road more than 2.5 km away is rejected rather than causing a huge detour. The logged off-road fallback remains.
- A generated local front places a nearby compatible alternate and friendly support behind the objective and hostile staging beyond it. This is a fictional local scenario, not a reconstruction of historical political boundaries or a complete war theater.
- Support orbit anchors and hostile air staging stay within planner bounds. Helicopter air starts use approximate terrain plus clearance; helicopter navigation waypoints use radio altitude. Jet cruise planning samples the route and adds clearance over public terrain. None of these checks certify DCS terrain, trees or obstacles.

Automatic alternates are constrained to nearby friendly fields. An explicitly selected coastal/isolated departure may need a longer alternate; the briefing explains that distance instead of switching your home silently. Explicit departure and target pins remain exact. A constrained pin can produce a placement warning or a clear error if the selected operation cannot fit. Coastlines and terrain legitimately limit some directions. Automatic planning retries bounded candidates rather than returning to the old fixed target.

Preview locks an automatically chosen seed for the next Generate only. After generation, another Generate gets a new variation. Automatic seeds are not saved as permanent replay preferences. Explicit recipe/manual seeds remain fixed and Quick setup labels them; New variation returns to fresh automatic layouts.

## Offline data and rebuilding

The app bundles cropped Natural Earth 1:10 million land/lakes/main-road rasters and public Mapzen terrain tile heights. Land pixels are roughly 80–130 m and heights roughly 340–520 m apart depending on latitude. Public roads differ from DCS roads; elevation cannot resolve individual buildings, small gullies or walls. No DCS imagery, terrain files or meshes were extracted. No download or account is required to use the screening. A bundled shaded relief map displays public terrain, coastlines, lakes and approximate main roads; it is not authentic DCS imagery. The map reserves space for coordinate/credit labels and colors airfields using actual generated ownership after Preview.

[Bundled credits](../../ironanvil/assets/geography/CREDITS.html) include provider notices, USGS/NOAA and Copernicus EU-DEM attribution, and Natural Earth's public-domain terms. **Data credits** in the app and the standalone mission briefing expose the notices to users. [Source hashes](../../ironanvil/assets/geography/source-sha256.json) identify the downloaded inputs.

Developers can rebuild using Python 3.12, `requirements-data.txt` and `python tools/build_geography_data.py`. Shapely/NumPy are developer-only dependencies, absent from the runtime requirements. The rebuild verifies recorded source hashes, uses an external cache, and preserves TLS verification. An intentional dataset refresh requires reviewing the changed source and passing `--refresh-sources`.

`python tools/report_geography.py --count 300 --output PATH` measures variation without building missions, rendering kneeboards or compiling Windows. `--baseline FILE` accepts the saved old-planner samples for its comparison diagram. Statistical results and real-flight checks are recorded in PROGRESS.md; geography tests assert reproducibility, diversity, explicit constraints and known terrain/water samples.
