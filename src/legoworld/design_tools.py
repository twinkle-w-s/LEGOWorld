"""Connector-driven placement and reversible local edits for the MCP host."""

from copy import deepcopy
import json
import math
from typing import Literal

from mcp.server.fastmcp import Image
from lego_mcp import connectors, parts
from lego_mcp import server as engine

from legoworld.catalog import RECORDS, bottom_origin
from legoworld.geometry import render_png
from legoworld.precision import collision_report

Rotation = Literal["identity", "rot90y", "rot180y", "rot270y"]
ROTATIONS = ("identity", "rot90y", "rot180y", "rot270y")


def get_connectors(part_id: str, instance_id: str | None = None) -> dict:
    """List indexed upright stud/receiver points in bottom-origin LDU, optionally world coordinates."""
    engine._require_part(part_id)
    instance = engine.STATE.parts[instance_id] if instance_id else None
    if instance and instance.part_id != part_id:
        raise ValueError("instance_id must refer to this part_id")
    definition = connectors.definition_for(part_id)
    result = []
    for index, point in enumerate(definition.connectors):
        local = (point.x, point.y, point.z)
        record = {"index": index, "type": point.type.value, "local": local}
        if instance:
            rotated = engine.matrix_apply(engine.effective_matrix(instance), local)
            record["world"] = [rotated[i]+(instance.x, instance.y, instance.z)[i] for i in range(3)]
        result.append(record)
    return {"part_id": part_id, "connectors": result,
            "scope": "Upright stud/receiver only; no pin, hinge, axle or side-stud attachment."}


def get_part_info(part_id: str) -> dict:
    """Get dimensions, category, exact upright connectors and the LDraw origin conversion."""
    result = engine.get_part_info(part_id)
    result.update({"category": RECORDS[part_id]["category"], "ldraw_bottom_origin": bottom_origin(part_id),
                   "connector_layout": get_connectors(part_id)["connectors"]})
    return result


def preview_placement(part_id: str, x: float, y: float, z: float,
                      rotation: Rotation = "identity", color: str = "light_bluish_gray") -> dict:
    """Check a proposed part without changing the model; return actual collisions and connection counts."""
    part = engine._require_part(part_id)
    if rotation not in ROTATIONS:
        raise ValueError("Only upright quarter-turn Y rotations are supported")
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise ValueError("Coordinates must be finite")
    candidate = engine.PartInstance("_preview", part_id, parts.resolve_color(color), x, y, z, rotation)
    collision = collision_report([*engine.STATE.parts.values(), candidate])
    hits = [a if b == "_preview" else b for a, b in collision["pairs"] if "_preview" in (a, b)]
    connection = engine._connection_report(candidate, part)
    grid_ok = all(abs(v-round(v/step)*step) < .1 for v, step in ((x, 10), (z, 10), (y, 2)))
    checked = collision["verified"] or collision["backend"] == "aabb"
    return {"ok": checked and not hits and connection["is_connected"] and grid_ok,
            "position": [x, y, z], "rotation": rotation, "collisions": hits,
            "collision": collision, "connectivity": connection, "grid_aligned": grid_ok}


def _attachment(base_instance_id, base_connector, part_id, part_connector, rotation):
    base = engine.STATE.parts[base_instance_id]
    base_points = get_connectors(base.part_id, base_instance_id)["connectors"]
    new_points = get_connectors(part_id)["connectors"]
    if not (0 <= base_connector < len(base_points) and 0 <= part_connector < len(new_points)):
        raise ValueError("Connector index out of range; use get_connectors")
    a, b = base_points[base_connector], new_points[part_connector]
    if a["type"] == b["type"]:
        raise ValueError("A stud must mate with a receiver")
    offset = engine.matrix_apply(engine.resolve_rotation(rotation), b["local"])
    return [a["world"][i]-offset[i] for i in range(3)]


def attach_part(base_instance_id: str, base_connector: int, part_id: str,
                part_connector: int, color: str = "light_bluish_gray",
                rotation: Rotation = "identity") -> dict:
    """Align two selected complementary connectors exactly and strictly place the new part."""
    position = _attachment(base_instance_id, base_connector, part_id, part_connector, rotation)
    preview = preview_placement(part_id, *position, rotation, color)
    if not preview["ok"]:
        return {"ok": False, "preview": preview}
    return engine.add_part(part_id, color, *position, rotation=rotation, strict=True)


_PLACEMENTS = {}
_SEQUENCE = 0


def find_valid_placements(part_id: str, near_part_id: str, limit: int = 20) -> dict:
    """Find exact connector-aligned placements, including asymmetric slopes and jumper plates.

    Searches at most 500 distinct poses per call. Tokens are rechecked when used.
    """
    global _SEQUENCE
    base = engine.STATE.parts[near_part_id]
    a = get_connectors(base.part_id)["connectors"]
    b = get_connectors(part_id)["connectors"]
    seen, choices = set(), []
    for rotation in ROTATIONS:
        for aa in a:
            for bb in b:
                if aa["type"] == bb["type"]:
                    continue
                pos = _attachment(near_part_id, aa["index"], part_id, bb["index"], rotation)
                key = (*pos, rotation)
                if key in seen:
                    continue
                seen.add(key)
                result = preview_placement(part_id, *pos, rotation)
                if result["ok"]:
                    _SEQUENCE += 1
                    token = f"v2pl{_SEQUENCE}"
                    _PLACEMENTS[token] = (part_id, pos, rotation)
                    choices.append({"token": token, "position": pos, "rotation": rotation,
                                    "studs_matched": result["connectivity"]["studs_engaged"]})
                if len(seen) >= 500 or len(choices) >= max(1, min(limit, 30)):
                    break
            if len(seen) >= 500 or len(choices) >= max(1, min(limit, 30)):
                break
        if len(seen) >= 500 or len(choices) >= max(1, min(limit, 30)):
            break
    while len(_PLACEMENTS) > 256:
        _PLACEMENTS.pop(next(iter(_PLACEMENTS)))
    return {"placements": choices, "count": len(choices), "poses_checked": len(seen),
            "search_truncated": len(seen) >= 500}


def add_part_at_placement(token: str, color: str = "light_bluish_gray") -> dict:
    """Strictly place a proposal from find_valid_placements, rechecking current state."""
    part_id, pos, rotation = _PLACEMENTS[token]
    preview = preview_placement(part_id, *pos, rotation, color)
    if not preview["ok"]:
        return {"ok": False, "preview": preview}
    return engine.add_part(part_id, color, *pos, rotation=rotation, strict=True)


def place_on_top(base_instance_id: str, new_part_id: str,
                 color: str = "light_bluish_gray") -> dict:
    """Place using a real top stud and a bottom receiver; use attach_part to choose the exact pair."""
    base = engine.STATE.parts[base_instance_id]
    tops = [p for p in get_connectors(base.part_id)["connectors"] if p["type"] == "stud_top"]
    bottoms = [p for p in get_connectors(new_part_id)["connectors"] if p["type"] == "stud_receiver_bottom"]
    for a in tops:
        for b in bottoms:
            pos = _attachment(base_instance_id, a["index"], new_part_id, b["index"], "identity")
            if preview_placement(new_part_id, *pos, color=color)["ok"]:
                return engine.add_part(new_part_id, color, *pos, strict=True)
    return {"ok": False, "reason": "No valid identity-rotation top attachment; try attach_part with another rotation."}


def _finish_edit(before):
    try:
        report = engine.validate_model()
    except Exception:
        engine.STATE = before
        raise
    if not report["valid"] or not report["structurally_sound"]:
        engine.STATE = before
        return {"ok": False, "rolled_back": True, "validation": report}
    return {"ok": True, "validation": report}


def replace_part(instance_id: str, part_id: str, color: str | None = None) -> dict:
    """Replace at the same bottom origin and rotation; roll back the entire state if invalid."""
    engine._require_part(part_id)
    resolved = parts.resolve_color(color) if color is not None else None
    instance = engine.STATE.parts[instance_id]
    before = deepcopy(engine.STATE)
    instance.part_id = part_id
    if resolved is not None:
        instance.color = resolved
    return _finish_edit(before)


def transform_group(instance_ids: list[str], dx: float = 0, dy: float = 0, dz: float = 0,
                    quarter_turns: int = 0, pivot_x: float = 0, pivot_z: float = 0) -> dict:
    """Translate/rotate a selected group in one transaction; invalid results restore the prior state."""
    selected = [engine.STATE.parts[i] for i in set(instance_ids)]
    if not selected:
        raise ValueError("Select at least one part")
    if any(p.matrix is not None or p.rotation not in ROTATIONS for p in selected):
        raise ValueError("Group transforms require upright authored parts")
    if not all(math.isfinite(v) for v in (dx, dy, dz, pivot_x, pivot_z)):
        raise ValueError("Transform values must be finite")
    before = deepcopy(engine.STATE)
    rotation = engine.resolve_rotation(ROTATIONS[quarter_turns % 4])
    for instance in selected:
        x, _, z = engine.matrix_apply(rotation, (instance.x-pivot_x, 0, instance.z-pivot_z))
        instance.x, instance.y, instance.z = x+pivot_x+dx, instance.y+dy, z+pivot_z+dz
        instance.rotation = ROTATIONS[(ROTATIONS.index(instance.rotation)+quarter_turns) % 4]
    return _finish_edit(before)


def inspect_part(instance_id: str) -> dict:
    """Inspect pose, world connectors, occupied bounds, neighbors and collision feedback."""
    instance = engine.STATE.parts[instance_id]
    return {"part": engine._inst_dict(instance),
            "bounds": engine.part_aabb_world(instance, engine.PART_INDEX[instance.part_id]),
            "connectors": get_connectors(instance.part_id, instance_id)["connectors"],
            "feedback": engine._placement_feedback(instance, engine.PART_INDEX[instance.part_id])}


def describe_errors(max_errors: int = 10) -> dict:
    """Describe current geometry/connection errors and the poses of affected instances."""
    report = engine.validate_model(max_errors=max_errors)
    poses = {}
    for error in report["errors"]:
        for key in ("instance_a", "instance_b", "instanceId", "instance_id"):
            iid = error.get(key)
            if iid in engine.STATE.parts:
                poses[iid] = engine._inst_dict(engine.STATE.parts[iid])
    return {"summary": report["summary"], "errors": report["errors"],
            "affected_parts": poses, "collision": report["collision"]}


def measure_model(instance_ids: list[str] | None = None) -> dict:
    """Measure logical body bounds and center in LDU, studs and millimeters (1 LDU = 0.4 mm)."""
    selected = list(engine.STATE.parts) if instance_ids is None else instance_ids
    if not selected:
        return {"parts": 0}
    boxes = [engine.part_aabb_world(engine.STATE.parts[i], engine.PART_INDEX[engine.STATE.parts[i].part_id]) for i in selected]
    low = [min(b[0][i] for b in boxes) for i in range(3)]
    high = [max(b[1][i] for b in boxes) for i in range(3)]
    size = [high[i]-low[i] for i in range(3)]
    return {"parts": len(selected), "bounds": [low, high], "size_ldu": size,
            "size_studs": [v/20 for v in size], "size_mm": [v*.4 for v in size]}


def render_view(azimuth: float = 35, elevation: float = 28, instance_ids: list[str] | None = None) -> list:
    """Return actual LDraw geometry as a native MCP image; optionally isolate selected parts."""
    if not all(math.isfinite(v) for v in (azimuth, elevation)) or not -89 <= elevation <= 89:
        raise ValueError("Use finite camera angles and elevation between -89 and 89 degrees")
    return [json.dumps({"renderer": "ldraw", "azimuth": azimuth, "elevation": elevation}),
            Image(data=render_png(azimuth, elevation, 900, 650, instance_ids), format="png")]


def register(mcp):
    for function in (get_part_info, get_connectors, preview_placement, attach_part,
                     find_valid_placements, add_part_at_placement, place_on_top, replace_part,
                     transform_group, inspect_part, describe_errors, measure_model, render_view):
        mcp.add_tool(function)
