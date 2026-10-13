"""Small, bounded scenery schema shared by the browser and Unreal previews."""

import math
import re

SCENE_TYPES = {"house", "pine", "box", "cone", "arch", "arches"}
ENVIRONMENT = {"skyColor": "#152238", "groundColor": "#8398b2", "snowfall": True,
               "glow": True, "groundVisible": True, "exposure": 1.2}


def default_scene(fixture_ids):
    """Give older fixture-only files the same editable scenery as the demo."""
    known = set(fixture_ids)
    objects = []

    def add(object_id, name, kind, position, scale, color, bindings=()):
        objects.append({"id": object_id, "name": name, "type": kind, "position": list(position),
                        "rotation": [0, 0, 0], "scale": list(scale), "color": color,
                        "fixtureIds": [value for value in bindings if value in known]})

    add("house", "House", "house", (0, 0, 0), (1, 1, 1), "#354251", ("roofline", "windows", "door"))
    for index, (x, z, radius_scale, height) in enumerate(((-11, -5, 5, 7), (-14, 1, 3.6, 5),
                                                         (12, -4, 4.6, 6), (15, -8, 5.2, 8))):
        add(f"background-pine-{index + 1}", f"Background pine {index + 1}", "pine",
            (x, 0, z), (radius_scale, height, radius_scale), "#173d39")
    for index, (x, fixture_id) in enumerate(((-7, "mini-left"), (-5, "mini-center"), (-3, "mini-right"))):
        add(f"mini-pine-{index + 1}", f"Mini pine {index + 1}", "pine", (x, 0, 3.8),
            (.9, 1.25, .9), "#174f43", (fixture_id,))
    add("mega-tree", "Mega tree", "cone", (6.5, 0, 1.3), (3.3, 5.8, 3.3), "#123a35", ("megatree", "star"))
    add("arches", "Three arches", "arches", (1.3, .08, 5), (1, 1, 1), "#45536a", ("arches",))
    add("walkway", "Walkway", "box", (0, -.052, 3.2), (1.25, .012, 6), "#70839a", ("path",))
    return {"version": 1, "environment": dict(ENVIRONMENT), "objects": objects}


def _color(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{name} must be a six-digit hex color")
    return value.lower()


def _vector(value, name, minimum, maximum):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain three numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
           or not minimum <= item <= maximum for item in value):
        raise ValueError(f"{name} must contain finite numbers between {minimum} and {maximum}")
    return [float(item) for item in value]


def validate_scene(data, fixture_ids):
    if not isinstance(data, dict) or isinstance(data.get("version"), bool) or data.get("version", 1) != 1:
        raise ValueError("scene must be an object with version 1")
    if set(data) - {"version", "environment", "objects"}:
        raise ValueError("unknown scene field")
    environment = data.get("environment", {})
    if not isinstance(environment, dict) or set(environment) - set(ENVIRONMENT):
        raise ValueError("invalid scene environment")
    normalized_environment = dict(ENVIRONMENT)
    normalized_environment.update(environment)
    for field in ("skyColor", "groundColor"):
        normalized_environment[field] = _color(normalized_environment[field], field)
    for field in ("snowfall", "glow", "groundVisible"):
        if not isinstance(normalized_environment[field], bool):
            raise ValueError(f"{field} must be a boolean")
    exposure = normalized_environment["exposure"]
    if isinstance(exposure, bool) or not isinstance(exposure, (int, float)) or not math.isfinite(exposure) or not .1 <= exposure <= 3:
        raise ValueError("scene exposure must be from 0.1 to 3")
    objects = data.get("objects")
    if not isinstance(objects, list) or len(objects) > 100:
        raise ValueError("scene objects must be an array with at most 100 objects")
    known, seen, bound, normalized = set(fixture_ids), set(), set(), []
    for item in objects:
        if not isinstance(item, dict) or set(item) - {"id", "name", "type", "position", "rotation", "scale", "color", "fixtureIds"}:
            raise ValueError("invalid scene object fields")
        object_id = item.get("id")
        if not isinstance(object_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", object_id) or object_id in seen:
            raise ValueError("scene object IDs must be unique strings of letters, digits, '-' and '_'")
        seen.add(object_id)
        name, kind = item.get("name", object_id), item.get("type")
        if not isinstance(name, str) or not 1 <= len(name) <= 120:
            raise ValueError("scene object names must contain 1 to 120 characters")
        if not isinstance(kind, str) or kind not in SCENE_TYPES:
            raise ValueError("unknown scene object type")
        bindings = item.get("fixtureIds", [])
        if not isinstance(bindings, list) or any(not isinstance(value, str) or value not in known for value in bindings):
            raise ValueError("scene fixtureIds must contain known fixture IDs")
        if len(set(bindings)) != len(bindings) or bound.intersection(bindings):
            raise ValueError("each fixture can be linked to only one scene object")
        bound.update(bindings)
        normalized.append({"id": object_id, "name": name, "type": kind,
                           "position": _vector(item.get("position", [0, 0, 0]), "position", -1000, 1000),
                           "rotation": _vector(item.get("rotation", [0, 0, 0]), "rotation", -360, 360),
                           "scale": _vector(item.get("scale", [1, 1, 1]), "scale", .001, 1000),
                           "color": _color(item.get("color", "#354251"), "object color"),
                           "fixtureIds": list(bindings)})
    return {"version": 1, "environment": normalized_environment, "objects": normalized}
