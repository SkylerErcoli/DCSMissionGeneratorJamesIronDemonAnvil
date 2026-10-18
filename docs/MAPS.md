# Map help

For ordinary mission creation, zoom the map with the mouse wheel or **+ / −**, drag to pan, and click to pin a target. **Fit map** restores the full view. Right-click the map or use **Clear** to remove the target. Decimal latitude and longitude can also be entered directly.

## Offline and internet maps

The offline background contains coastlines, country boundaries, cities, coordinate grids, and airbase markers. Its Natural Earth geography is public domain and uses coarse coastlines. Choose an inland point and check the local terrain in the DCS Mission Editor.

**Internet map (OSM)** adds OpenStreetMap roads, towns, and geographic detail. It needs internet access to `https://tile.openstreetmap.org`; downloaded visible tiles are cached locally. If the service cannot be reached, the app falls back to the offline background. Both backgrounds show geographic information rather than DCS artwork, so scenery and some details differ from the simulator.

## Optional: import a DCS chart

This section is for users who already have a correctly georeferenced chart. Importing a chart is not required to generate missions. No proprietary DCS chart imagery is bundled or automatically extracted from DCS.

**Import DCS chart...** overlays a local, north-up, georeferenced image. The app remembers a separate image for each theatre. Enter the image's geographic bounds and projection when asked, or place a metadata file beside the image. For an image named `mychart.png`, name the metadata file `mychart.png.json`:

```json
{"bounds": [7.0, 49.0, 17.0, 55.5], "crs": "EPSG:4326"}
```

The numbers above only illustrate Germany-area bounds. They do not calibrate an arbitrary picture. Use the actual geographic extent of your image, in **west, south, east, north** order, in decimal degrees.

Supported projections are:

| Projection | Image layout |
| --- | --- |
| `EPSG:4326` | Equirectangular: image rows are evenly spaced in latitude. |
| `EPSG:3857` | Web Mercator. |

Bounds are geographic degrees for either projection. A raw F10 screenshot must first be georeferenced and rectified to one of these projections. Importing a screenshot and guessing its bounds will not produce reliable target placement.

Map imagery does not establish DCS ground height, slope, or object clearance. Always check generated placements in the DCS Mission Editor before flying.
