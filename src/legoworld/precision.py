"""BrickNet convex collision adapter on the existing engine state."""

import os
import json
from functools import lru_cache
from importlib.metadata import distribution
from itertools import combinations, product

# Small pose matrices do not benefit from BLAS thread pools. This also avoids
# Windows native-library initialization stalls in stdio child processes.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
from lego_mcp import server as engine

from legoworld.assets import collider_root
from legoworld.catalog import RECORDS, bottom_origin

LEGACY_VALIDATE = engine.validate_model
LEGACY_COLLISIONS = engine._collisions_for


def mode() -> str:
    value = os.environ.get("LEGOWORLD_COLLISION", "bricknet")
    if value not in ("bricknet", "aabb"):
        raise ValueError("LEGOWORLD_COLLISION must be bricknet or aabb")
    return value


def ldraw_matrix(instance) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(engine.effective_matrix(instance)).reshape(3, 3)
    matrix[:3, 3] = (instance.x, instance.y, instance.z) - matrix[:3, :3] @ bottom_origin(instance.part_id)
    return matrix


def collision_report(instances=None) -> dict:
    instances = list(engine.STATE.parts.values() if instances is None else instances)
    if mode() == "aabb":
        instances = [p for p in instances if p.part_id in engine.PART_INDEX]
        pairs = [[a.instance_id, b.instance_id] for i, a in enumerate(instances) for b in instances[i+1:]
                 if engine.aabbs_overlap(engine.part_aabb_world(a, engine.PART_INDEX[a.part_id]),
                                         engine.part_aabb_world(b, engine.PART_INDEX[b.part_id]))]
        return {"backend": "aabb", "verified": False, "pairs": pairs, "missing": [],
                "note": "Explicit conservative fallback; not precise geometry verification."}
    os.environ["BRICKNET_DATA"] = str(collider_root())
    missing = [p.instance_id for p in instances if p.part_id not in RECORDS or
               not (collider_root()/"cvx"/(RECORDS[p.part_id]["collider"]+".cvx.obj")).is_file()]
    try:
        from bricknet.collision import colliding_pairs
        from bricknet.data import load_catalog
        from bricknet import data
    except ImportError as error:
        return {"backend": "bricknet", "verified": False, "pairs": [], "missing": missing,
                "reason": f"Install .[precision]: {error}"}
    # BrickNet 0.1.1 uses the Windows locale to read its UTF-8 name table.
    # Keep this compatibility fix inside the pinned adapter, not site-packages.
    data._part_names = _utf8_names
    catalog = load_catalog()
    if missing:
        return {"backend": "bricknet", "verified": False, "pairs": [], "missing": missing,
                "reason": "Missing colliders; run legoworld fetch-assets."}
    matrices = []
    for p in instances:
        values = RECORDS[p.part_id]["collider_transform"]
        wrapper = np.eye(4)
        wrapper[:3, 3] = values[:3]
        wrapper[:3, :3] = np.array(values[3:]).reshape(3, 3)
        matrices.append(ldraw_matrix(p) @ wrapper)
    # Coincident compound baseplates can overflow Bullet's native contact
    # buffer. Detect duplicates exactly and query each distinct pose once.
    groups = {}
    for p, matrix in zip(instances, matrices):
        key = (RECORDS[p.part_id]["collider"], matrix.tobytes())
        groups.setdefault(key, []).append(p.instance_id)
    keys = list(groups)
    pairs = colliding_pairs([catalog.stem_to_id[key[0]] for key in keys],
                            [np.frombuffer(key[1], dtype=float).reshape(4, 4) for key in keys])
    named_pairs = [list(pair) for ids in groups.values() for pair in combinations(ids, 2)]
    named_pairs += [list(pair) for i, j in (pairs or []) for pair in product(groups[keys[i]], groups[keys[j]])]
    return {"backend": "bricknet", "verified": pairs is not None, "missing": [],
            "tolerance_ldu": 1.0,
            "pairs": named_pairs}


@lru_cache(maxsize=1)
def _utf8_names():
    path = distribution("bricknet").locate_file("bricknet/_data/v1/part_names.json")
    return json.loads(path.read_text(encoding="utf-8"))


def collisions_for(instance, part):
    if mode() == "aabb":
        return LEGACY_COLLISIONS(instance, part)
    others = [p for p in engine.STATE.parts.values() if p.instance_id != instance.instance_id]
    report = collision_report([instance, *others])
    if not report["verified"]:
        raise ValueError(f"Collision check unverified: {report}")
    return [b if a == instance.instance_id else a for a, b in report["pairs"]
            if instance.instance_id in (a, b)]


def validate_model(max_errors: int = 200, check_support: bool = True) -> dict:
    """Combine existing stud/ground checks with convex geometry penetration."""
    # Do not let a truncated list of conservative collisions hide support errors.
    report = LEGACY_VALIDATE(max_errors=max(100000, max_errors), check_support=check_support)
    collision = collision_report()
    errors = [e for e in report["errors"] if e["type"] != "collision"]
    errors += [{"type": "collision", "instance_a": a, "instance_b": b,
                "note": collision["backend"]} for a, b in collision["pairs"]]
    if mode() == "bricknet" and not collision["verified"]:
        errors.append({"type": "collision_unverified", "details": collision})
    report["errors"] = errors[:max_errors]
    report["summary"]["collisions"] = len(collision["pairs"])
    report["summary"]["errors_truncated"] = len(errors) > max_errors
    report["valid"] = not errors
    report["structurally_sound"] = report["valid"] and report.get("summary", {}).get("rigid_bodies", 1) <= 1
    report["collision"] = collision
    report["connection_scope"] = "Upright stud/receiver connections; no clutch-force or load simulation."
    return report


def install() -> None:
    # Shared hook used by strict add, helpers, moves, reviews and export.
    engine._collisions_for = collisions_for
    engine.validate_model = validate_model
