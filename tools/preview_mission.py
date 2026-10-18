#!/usr/bin/env python3
"""Draw a shareable plan-view PNG from an actual .miz archive.

This is a layout schematic, not terrain imagery. DCS runs are still required to
check elevation, obstacles, parking, weapons, and behavior in the simulator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont
from dcs import Mission


def mission_objects(mission):
    """Yield actual pydcs group/unit positions after loading the archive."""
    for side, coalition in mission.coalition.items():
        for country in coalition.countries.values():
            for category in ("vehicle", "static", "plane", "helicopter", "ship"):
                for group in getattr(country, f"{category}_group"):
                    for unit in group.units:
                        yield side, category, group.name, unit


def preview(miz_path, output_path=None, span_km=4, overview=False):
    miz_path = Path(miz_path)
    mission = Mission()
    mission.load_file(str(miz_path))
    with zipfile.ZipFile(miz_path) as archive:
        metadata = json.loads(archive.read("ironanvil.json")) if "ironanvil.json" in archive.namelist() else {}
    objects = list(mission_objects(mission))
    if not objects:
        raise ValueError("This mission contains no objects to preview")
    # DCS coordinates use x for north and y for east. Keep north at the top.
    target = metadata.get("runtime", {}).get("target")
    if target and not overview:
        centre_east, centre_north = target["z"], target["x"]
    else:
        centre_east = (min(u.position.y for *_, u in objects) + max(u.position.y for *_, u in objects)) / 2
        centre_north = (min(u.position.x for *_, u in objects) + max(u.position.x for *_, u in objects)) / 2
    width, height = 1400, 1000
    margins = (70, 105, 45, 85)
    plot_width, plot_height = width - margins[0] - margins[2], height - margins[1] - margins[3]
    if overview or not target:
        north_range = max(u.position.x for *_, u in objects) - min(u.position.x for *_, u in objects)
        east_range = max(u.position.y for *_, u in objects) - min(u.position.y for *_, u in objects)
        span = max(east_range * 1.2, north_range * plot_width / plot_height * 1.2, 1000)
    else:
        span = span_km * 1000
    scale = plot_width / span

    def position(point):
        return (margins[0] + plot_width / 2 + (point.y - centre_east) * scale,
                margins[1] + plot_height / 2 - (point.x - centre_north) * scale)

    canvas = Image.new("RGB", (width, height), "#101b27")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=15)
    small = ImageFont.load_default(size=12)
    title_font = ImageFont.load_default(size=24)
    draw.text((35, 22), "IRON ANVIL · MISSION LAYOUT", fill="#f6ead2", font=title_font)
    draw.text((35, 58), f"{miz_path.name}  |  {mission.terrain.name}  |  "
              f"{'mission overview' if overview else 'objective area'}", fill="#b9c8d6", font=font)
    draw.rectangle((margins[0], margins[1], width - margins[2], height - margins[3]),
                   fill="#1c2c34", outline="#59707d")
    step_m = 1000 if span <= 15000 else 10000
    for east in range(int((centre_east - span / 2) // step_m) * step_m,
                      int(centre_east + span / 2) + step_m, step_m):
        x = margins[0] + plot_width / 2 + (east - centre_east) * scale
        if margins[0] <= x <= width - margins[2]:
            draw.line((x, margins[1], x, height - margins[3]), fill="#33434b")
    north_span = plot_height / scale
    for north in range(int((centre_north - north_span / 2) // step_m) * step_m,
                       int(centre_north + north_span / 2) + step_m, step_m):
        y = margins[1] + plot_height / 2 - (north - centre_north) * scale
        if margins[1] <= y <= height - margins[3]:
            draw.line((margins[0], y, width - margins[2], y), fill="#33434b")
    colours = {"blue": "#59bcff", "red": "#ff806e", "neutrals": "#e1d59b"}
    labelled = set()
    label_boxes = []
    shown, omitted = 0, 0
    for side, category, group_name, unit in objects:
        x, y = position(unit.position)
        if not (margins[0] + 6 <= x <= width - margins[2] - 6 and
                margins[1] + 6 <= y <= height - margins[3] - 6):
            omitted += 1
            continue
        shown += 1
        colour = colours.get(side, "#e1d59b")
        if category in ("plane", "helicopter"):
            draw.polygon(((x, y - 7), (x - 6, y + 6), (x + 6, y + 6)), fill=colour)
        elif category == "static":
            draw.rectangle((x - 3, y - 3, x + 3, y + 3), fill=colour)
        else:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colour)
        # Limit clutter while preserving labels on the significant groups.
        if group_name not in labelled and category != "static":
            text_width = draw.textlength(group_name, font=small)
            candidates = [(anchor, y + delta) for delta in (-16, -36, 10, -56, 30, -76, 50, 70, -96, 90)
                          for anchor in (x + 10, x - text_width - 10)]
            for text_x, text_y in candidates:
                box = (text_x - 3, text_y - 2, text_x + text_width + 3, text_y + 16)
                if not (margins[0] < box[0] and box[2] < width - margins[2] and
                        margins[1] < box[1] and box[3] < height - margins[3]):
                    continue
                if any(box[0] < other[2] and box[2] > other[0] and
                       box[1] < other[3] and box[3] > other[1] for other in label_boxes):
                    continue
                label_boxes.append(box)
                nearest_x = min(max(x, text_x), text_x + text_width)
                draw.line((x, y, nearest_x, text_y + 8), fill=colour)
                draw.rectangle(box, fill="#1c2c34")
                draw.text((text_x, text_y), group_name, fill=colour, font=small)
                break
            labelled.add(group_name)
    if target:
        from dcs.mapping import Point
        x, y = position(Point(target["x"], target["z"], mission.terrain))
        if margins[0] <= x <= width - margins[2] and margins[1] <= y <= height - margins[3]:
            draw.ellipse((x - 12, y - 12, x + 12, y + 12), outline="#ffe28b", width=2)
            draw.line((x - 17, y, x + 17, y), fill="#ffe28b", width=2)
            draw.line((x, y - 17, x, y + 17), fill="#ffe28b", width=2)
    # A scale bar and north arrow make the coordinate projection explicit.
    bar_m = step_m
    bar_x, bar_y = margins[0] + 18, height - margins[3] - 28
    draw.line((bar_x, bar_y, bar_x + bar_m * scale, bar_y), fill="#f6ead2", width=3)
    draw.text((bar_x, bar_y - 22), f"{bar_m / 1000:g} km", fill="#f6ead2", font=small)
    arrow_x = width - 75
    draw.text((arrow_x - 5, 120), "N", fill="#f6ead2", font=font)
    draw.line((arrow_x, 170, arrow_x, 145), fill="#f6ead2", width=2)
    draw.polygon(((arrow_x, 141), (arrow_x - 5, 150), (arrow_x + 5, 150)), fill="#f6ead2")
    draw.text((35, height - 65), f"Blue: friendly   Red: enemy   Square: static   Circle: ground unit   Triangle: aircraft   "
              f"{shown} objects shown, {omitted} outside view", fill="#b9c8d6", font=small)
    draw.text((35, height - 38), "Schematic from actual .miz positions; terrain, elevation and obstacles are omitted. "
              "Use --overview for the whole mission.", fill="#b9c8d6", font=small)
    output_path = Path(output_path) if output_path else miz_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mission", type=Path, help="Existing .miz archive")
    parser.add_argument("--output", type=Path, help="Output PNG (default: beside the mission)")
    parser.add_argument("--span-km", type=float, default=4, help="Objective view width in kilometres")
    parser.add_argument("--overview", action="store_true", help="Fit all mission objects")
    args = parser.parse_args()
    if args.span_km <= 0:
        parser.error("--span-km must be positive")
    print(preview(args.mission, args.output, args.span_km, args.overview))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
