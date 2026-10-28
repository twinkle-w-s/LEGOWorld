"""BrickAgent catalog filtered by recursively available local geometry/colliders."""

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from legoworld.backend import b, tables
from legoworld.assets import ldraw_root, collider_root

COMMON = frozenset(json.loads((files("legoworld") / "catalog.json").read_text(encoding="utf-8")))


class GeometryIndex:
    def __init__(self, root):
        self.root = Path(root)
        self.records = {}

    def problem(self, name, visiting=frozenset(), checked=None):
        name = name.lower().replace("\\", "/")
        checked = {} if checked is None else checked
        if name in checked:
            return checked[name]
        if name in visiting:
            return f"Cyclic geometry reference: {name}"
        if ".." in name.split("/") or name.startswith("/") or ":" in name:
            return f"Invalid geometry reference: {name}"
        path = next((p for p in (self.root / "parts" / name, self.root / "p" / name) if p.is_file()), None)
        if path is None:
            return f"Missing geometry: {name}"
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        record = self.records.get(name)
        if record is None or record[0] != signature:
            refs = []
            for line in path.read_text(encoding="latin-1").splitlines():
                tokens = line.split()
                if len(tokens) >= 15 and tokens[0] == "1":
                    refs.append(" ".join(tokens[14:]))
            record = self.records[name] = (signature, tuple(refs))
        for ref in record[1]:
            problem = self.problem(ref, visiting | {name}, checked)
            if problem:
                checked[name] = problem
                return problem
        checked[name] = None
        return None


@lru_cache(maxsize=4)
def geometry_index(root):
    return GeometryIndex(root)


def asset_status(part_id, checked=None):
    stem = b.resolve(part_id)
    geometry = geometry_index(str(ldraw_root().resolve())).problem(stem + ".dat", checked=checked)
    collider = collider_root() / "cvx" / (stem + ".cvx.obj")
    problems = ([geometry] if geometry else []) + ([] if collider.is_file() else [f"Missing collider: {collider.name}"])
    return {"part_id": stem, "available": not problems, "problems": problems}


@lru_cache(maxsize=1)
def common_stems():
    return frozenset(b.resolve(s) for s in COMMON)


def search(query="", limit=20, offset=0, common_only=False):
    if limit < 1 or limit > 100 or offset < 0:
        raise ValueError("Use limit 1..100 and a nonnegative offset")
    results, available, checked = [], 0, {}
    for stem in b.find(query):
        if common_only and stem not in common_stems():
            continue
        if not asset_status(stem, checked)["available"]:
            continue
        if available >= offset:
            results.append({"part_id": stem, "name": b.name(stem), "common": stem in common_stems()})
        available += 1
        if len(results) > limit:
            break
    return {"parts": results[:limit], "offset": offset, "has_more": len(results) > limit,
            "catalog_scope": "BrickAgent parts with complete local recursive geometry and colliders"}


def info(part_id):
    stem = b.resolve(part_id)
    return {**asset_status(stem), "name": b.name(stem), "bounds_ldu": b.measure(stem),
            "description": b.describe(stem), "common": stem in common_stems()}


def doctor(full=False):
    stems = b.find() if full else tuple(sorted(common_stems()))
    checked = {}
    statuses = [asset_status(s, checked) for s in stems]
    return {"catalog_parts": len(tables("bounds.json.xz")), "checked_parts": len(statuses),
            "available_parts": sum(s["available"] for s in statuses),
            "unavailable": [s for s in statuses if not s["available"]],
            "ldraw_library": str(ldraw_root()), "collider_library": str(collider_root()),
            "index_files_cached": len(geometry_index(str(ldraw_root().resolve())).records)}
