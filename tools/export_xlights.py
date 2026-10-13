#!/usr/bin/env python3
"""Export channel-preserving xLights custom models from the shared 3D layout.

The model is an approximate XY projection. Coincident/projected pixels are
placed in nearby distinct cells so every RGB node retains its wire index.
"""

import argparse
import csv
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lightshow.layout import load_layout  # noqa: E402


def nearby_cells(x, y):
    """Visit distinct cells in stable rings, beginning at the requested cell."""
    yield x, y
    radius = 1
    while True:
        perimeter = []
        for dx in range(-radius, radius + 1):
            perimeter.extend(((dx, -radius), (dx, radius)))
        for dy in range(-radius + 1, radius):
            perimeter.extend(((-radius, dy), (radius, dy)))
        for dx, dy in sorted(perimeter, key=lambda p: (p[0] ** 2 + p[1] ** 2, p[1], p[0])):
            yield x + dx, y + dy
        radius += 1


def project_fixture(fixture, cells_per_meter):
    occupied, searches, placements = set(), {}, []
    for point in fixture["pixels"]:
        target = (round(point[0] * cells_per_meter), round(-point[1] * cells_per_meter))
        search = searches.setdefault(target, nearby_cells(*target))
        cell = next(search)
        while cell in occupied:
            cell = next(search)
        occupied.add(cell)
        placements.append(cell)
    min_x = min(cell[0] for cell in placements)
    min_y = min(cell[1] for cell in placements)
    width = max(cell[0] for cell in placements) - min_x + 1
    height = max(cell[1] for cell in placements) - min_y + 1
    if width * height > 2_000_000 or max(width, height) > 4000:
        raise ValueError(f"{fixture['id']} projection is too large; reduce --cells-per-meter")
    grid = [[""] * width for _ in range(height)]
    for node, (x, y) in enumerate(placements, 1):
        grid[y - min_y][x - min_x] = str(node)
    # This is the essential export invariant: every wire node occurs once.
    values = [int(cell) for row in grid for cell in row if cell]
    if sorted(values) != list(range(1, len(fixture["pixels"]) + 1)):
        raise ValueError(f"{fixture['id']} export lost or duplicated a wire node")
    return width, height, ";".join(",".join(row) for row in grid)


def write_models(layout, output, cells_per_meter):
    projections = [(fixture, project_fixture(fixture, cells_per_meter))
                   for fixture in layout["fixtures"]]
    for fixture, (width, height, data) in projections:
        root = ET.Element("custommodel", {
            "name": fixture["name"], "DisplayAs": "Custom",
            "StringType": "RGB Nodes", "CustomStrings": "1",
            "StartChannel": str(fixture["startChannel"]),
            "CustomWidth": str(width), "CustomHeight": str(height),
            "parm1": str(width), "parm2": str(height), "Depth": "1",
            "PixelSize": "2", "Transparency": "0", "ModelBrightness": "0",
            "CustomModel": data,
            "Description": "Christmas Lights Visualizer XY projection; preserve RGB node order and verify StartChannel.",
        })
        ET.ElementTree(root).write(output / f"{fixture['id']}.xmodel",
                                   encoding="utf-8", xml_declaration=True)


def universe_slot(channel, universe_size, start_universe):
    return start_universe + (channel - 1) // universe_size, (channel - 1) % universe_size + 1


def write_maps(layout, output, universe_size, start_universe):
    with (output / "channel-map.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["fixture_id", "name", "pixels", "start_channel", "end_channel",
                         "ddp_offset_bytes", "start_universe", "start_slot",
                         "end_universe", "end_slot", "channels_per_universe"])
        for fixture in layout["fixtures"]:
            start = fixture["startChannel"]
            end = start + len(fixture["pixels"]) * 3 - 1
            writer.writerow([fixture["id"], fixture["name"], len(fixture["pixels"]),
                             start, end, start - 1,
                             *universe_slot(start, universe_size, start_universe),
                             *universe_slot(end, universe_size, start_universe), universe_size])
    with (output / "pixel-map.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["fixture_id", "node", "red_channel", "green_channel", "blue_channel",
                         "ddp_offset_bytes", "x_m", "y_m", "z_m"])
        for fixture in layout["fixtures"]:
            for node, point in enumerate(fixture["pixels"], 1):
                red = fixture["startChannel"] + (node - 1) * 3
                writer.writerow([fixture["id"], node, red, red + 1, red + 2, red - 1, *point])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, default=ROOT / "layouts/default.json")
    parser.add_argument("--output", type=Path, default=ROOT / "xlights")
    parser.add_argument("--cells-per-meter", type=float, default=25.0)
    parser.add_argument("--universe-size", type=int, choices=(510, 512), default=510)
    parser.add_argument("--start-universe", type=int, default=1)
    args = parser.parse_args()
    if not math.isfinite(args.cells_per_meter) or not 0.01 <= args.cells_per_meter <= 100:
        parser.error("--cells-per-meter must be between 0.01 and 100")
    layout = load_layout(args.layout)
    universe_count = math.ceil(layout["channelCount"] / args.universe_size)
    if not 1 <= args.start_universe <= 63999 or args.start_universe + universe_count - 1 > 63999:
        parser.error("export universes must lie between 1 and 63999")
    args.output.mkdir(parents=True, exist_ok=True)
    write_models(layout, args.output, args.cells_per_meter)
    write_maps(layout, args.output, args.universe_size, args.start_universe)
    print(f"Exported {len(layout['fixtures'])} custom models, {layout['pixelCount']} pixels, "
          f"{layout['channelCount']} RGB channels to {args.output}")


if __name__ == "__main__":
    main()
