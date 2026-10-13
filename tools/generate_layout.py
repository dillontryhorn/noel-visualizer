"""Create the shared, deterministic browser/Unreal sample in meters."""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lightshow.layout import validate_layout


def line(a, b, count):
    return [[round(a[j] + (b[j] - a[j]) * i / max(1, count - 1), 4)
             for j in range(3)] for i in range(count)]


def polyline(points, count_per_edge, closed=False):
    vertices = points + ([points[0]] if closed else [])
    output = []
    for a, b in zip(vertices, vertices[1:]):
        output.extend(line(a, b, count_per_edge + 1)[:-1])
    if not closed:
        output.append(list(vertices[-1]))
    return output


def tree(x, z, height, radius, strings, per_string):
    pixels = []
    for string in range(strings):
        angle = math.tau * string / strings
        base = [x + radius * math.cos(angle), 0.12, z + radius * math.sin(angle)]
        # Alternating wiring direction reflects a common serpentine pixel tree.
        strand = line(base, [x, height, z], per_string)
        pixels.extend(strand if string % 2 == 0 else strand[::-1])
    return pixels


def make_layout():
    fixtures, channel = [], 1

    def add(fixture_id, name, kind, points):
        nonlocal channel
        fixtures.append({"id": fixture_id, "name": name, "type": kind,
                         "startChannel": channel, "pixels": points})
        channel += len(points) * 3

    roof = polyline([[-4, 3.5, .07], [0, 5.8, .07], [4, 3.5, .07]], 48)
    roof += line([-4, 3.5, 0], [-4, 3.5, -4], 36)
    roof += line([4, 3.5, -4], [4, 3.5, 0], 36)
    roof += line([-4, 3.5, .07], [4, 3.5, .07], 73)
    add("roofline", "House roofline", "roofline", roof)
    windows = []
    for center in (-2.3, 2.3):
        windows += polyline([[center - .8, 1.25, .09], [center - .8, 2.75, .09],
                             [center + .8, 2.75, .09], [center + .8, 1.25, .09]], 16, True)
    add("windows", "Window frames", "windows", windows)
    add("door", "Entryway", "door", polyline([[-.625, .06, .1], [-.625, 2.4, .1],
                                               [.625, 2.4, .1], [.625, .06, .1]], 24))
    add("megatree", "16-strand mega tree", "tree", tree(6.5, 1.3, 6, 1.75, 16, 32))
    vertices = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        radius = .57 if i % 2 == 0 else .25
        vertices.append([6.5 + radius * math.cos(angle), 6.55 + radius * math.sin(angle), 1.38])
    add("star", "Tree topper", "star", polyline(vertices, 5, True))
    for fixture_id, name, x in (("mini-left", "Mini tree left", -7),
                                ("mini-center", "Mini tree center", -5),
                                ("mini-right", "Mini tree right", -3)):
        add(fixture_id, name, "tree", tree(x, 3.8, 1.4, .52, 6, 12))
    arches = []
    for center in (-1, 1.3, 3.6):
        arches += [[round(center + math.cos(math.pi - i * math.pi / 39), 4),
                    round(.08 + 1.2 * math.sin(i * math.pi / 39), 4), 5]
                   for i in range(40)]
    add("arches", "Three leaping arches", "arches", arches)
    add("path", "Walkway lights", "path", line([-.8, .08, 1], [-.8, .08, 6], 42)
        + line([.8, .08, 6], [.8, .08, 1], 42))
    return validate_layout({"name": "Evergreen Lane", "fixtures": fixtures})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "layouts" / "default.json")
    args = parser.parse_args()
    data = make_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {data['pixelCount']} pixels / {data['channelCount']} RGB channels to {args.output}")


if __name__ == "__main__":
    main()
