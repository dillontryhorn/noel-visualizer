"""Validate RGB fixtures and expose a single mapping to every renderer.

Coordinates are meters, with X horizontal, Y up, and positive Z toward the
viewer. Channels are one-based in the JSON; wire offsets are zero-based.
"""

import json
import hashlib
import math
from pathlib import Path

from .scene import default_scene, validate_scene

MAX_PIXELS = 20_000
MAX_CHANNELS = MAX_PIXELS * 3


def _integer(value, name, minimum=1, maximum=MAX_CHANNELS):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def validate_layout(data):
    """Return normalized fixtures; reject overlap, unbounded or non-finite data."""
    if not isinstance(data, dict) or not isinstance(data.get("fixtures"), list):
        raise ValueError("layout must be an object containing a fixtures array")
    fixtures = data["fixtures"]
    if not 1 <= len(fixtures) <= 256:
        raise ValueError("layout must contain 1 to 256 fixtures")
    name = data.get("name", "Custom display")
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        raise ValueError("layout name must be a string of 1 to 120 characters")
    normalized, seen, ranges = [], set(), []
    channel_count = pixel_count = next_channel = 0
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("every fixture must be an object")
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not 1 <= len(fixture_id) <= 64 or fixture_id in seen:
            raise ValueError("fixture IDs must be unique strings of 1 to 64 characters")
        if not all(c.isalnum() or c in "-_" for c in fixture_id):
            raise ValueError("fixture IDs may only contain letters, digits, '-' and '_'")
        seen.add(fixture_id)
        label, kind = fixture.get("name", fixture_id), fixture.get("type", "string")
        if not isinstance(label, str) or not 1 <= len(label) <= 120:
            raise ValueError(f"invalid name for fixture {fixture_id}")
        if not isinstance(kind, str) or not 1 <= len(kind) <= 40:
            raise ValueError(f"invalid type for fixture {fixture_id}")
        pixels = fixture.get("pixels")
        if not isinstance(pixels, list) or not pixels or len(pixels) > MAX_PIXELS:
            raise ValueError(f"fixture {fixture_id} requires a bounded, non-empty pixels array")
        points = []
        for point in pixels:
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                raise ValueError(f"fixture {fixture_id} pixels must be [x, y, z]")
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or abs(v) > 1000 for v in point):
                raise ValueError(f"fixture {fixture_id} has an invalid coordinate")
            points.append([float(v) for v in point])
        if "pixelCount" in fixture and _integer(fixture["pixelCount"], "fixture pixelCount", maximum=MAX_PIXELS) != len(points):
            raise ValueError(f"fixture {fixture_id} pixelCount does not match its pixels")
        start = _integer(fixture.get("startChannel", next_channel + 1), "startChannel")
        end = start - 1 + len(points) * 3
        if end > MAX_CHANNELS:
            raise ValueError("layout channel span is too large")
        for previous_start, previous_end in ranges:
            if start - 1 < previous_end and end > previous_start:
                raise ValueError(f"fixture {fixture_id} overlaps another fixture's channels")
        ranges.append((start - 1, end))
        pixel_count += len(points)
        if pixel_count > MAX_PIXELS:
            raise ValueError("layout has too many pixels")
        channel_count = max(channel_count, end)
        next_channel = end
        normalized.append({"id": fixture_id, "name": label, "type": kind,
                           "startChannel": start, "pixelCount": len(points), "pixels": points})
    if "pixelCount" in data and _integer(data["pixelCount"], "pixelCount", maximum=MAX_PIXELS) != pixel_count:
        raise ValueError("pixelCount does not match the fixture pixels")
    if "channelCount" in data:
        declared = _integer(data["channelCount"], "channelCount")
        if declared < channel_count:
            raise ValueError("channelCount is smaller than the fixture mapping")
        channel_count = declared
    universe_size = _integer(data.get("universeSize", 510), "universeSize", maximum=512)
    if universe_size not in (510, 512):
        raise ValueError("universeSize must be 510 or 512")
    start_universe = _integer(data.get("startUniverse", 1), "startUniverse", maximum=63999)
    universe_count = math.ceil(channel_count / universe_size)
    if start_universe + universe_count - 1 > 63999:
        raise ValueError("E1.31 universe range is outside 1 to 63999")
    scene = validate_scene(data["scene"], seen) if "scene" in data else default_scene(seen)
    return {"name": name, "version": 1, "units": "meters", "colorOrder": "RGB",
            "pixelCount": pixel_count, "channelCount": channel_count,
            "universeCount": universe_count, "universeSize": universe_size,
            "startUniverse": start_universe, "fixtures": normalized, "scene": scene}


def load_layout_snapshot(path):
    """Read the normalized layout and fingerprint from the same file contents."""
    path = Path(path)
    if path.stat().st_size > 8_000_000:
        raise ValueError("layout JSON exceeds 8 MB")
    contents = path.read_bytes()
    if len(contents) > 8_000_000:
        raise ValueError("layout JSON exceeds 8 MB")
    return validate_layout(json.loads(contents.decode("utf-8"))), hashlib.sha256(contents).digest()


def load_layout(path):
    return load_layout_snapshot(path)[0]


def pixel_mapping(layout):
    """Yield (channel offset, point, fixture ID, fixture-local pixel index)."""
    for fixture in layout["fixtures"]:
        start = fixture["startChannel"] - 1
        for index, point in enumerate(fixture["pixels"]):
            yield start + index * 3, point, fixture["id"], index

