"""Read-only inspection and small adapters over the V3 project."""

from itertools import product
import numpy as np

from legoworld.backend import b
from legoworld.document import entries, flat_records, owner
from legoworld.editing import endpoint, native_connector


def connector_data(c):
    return {"type": c.type, "index": c.index, "native_index": c.native_index,
            "kind": c.kind, "subtype": c.sub, "polarity": c.polarity,
            "position": list(c.at), "axis": list(c.axis), "frame": list(c.pose.rot),
            "half_length_ldu": c.length}


def get_connectors(document, part_id=None, node_id=None, offset=0, limit=100):
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("Use limit 1..500 and nonnegative offset")
    if (part_id is None) == (node_id is None):
        raise ValueError("Supply exactly one of part_id and node_id")
    if part_id is not None:
        points = [connector_data(c) for c in b.connectors(part_id)]
    else:
        item = entries(document)[node_id]
        if item["assembly"]:
            points = [{"port": name, **connector_data(native_connector(document, endpoint(document,
                {"node_id": node_id, "port": name})))} for name in owner(document, node_id)["ports"]]
        else:
            points = [connector_data(native_connector(document, endpoint(document,
                {"node_id": node_id, "type": c.type, "index": c.index}))) for c in b.connectors(item["part_id"])]
    return {"revision": document["revision"], "connectors": points[offset:offset+limit],
            "total": len(points), "has_more": offset+limit < len(points),
            "frame": "part-local" if part_id else "world"}


def measure(document, node_ids=None):
    known = entries(document)
    selected = set(known if node_ids is None else node_ids)
    if not selected <= known.keys():
        raise KeyError("Unknown node in measurement")
    flat = [p for p in flat_records(document) if any(p["id"] == i or p["id"].startswith(i + "/") for i in selected)]
    if not flat:
        return {"parts": 0}
    points = []
    for p in flat:
        lo, hi = b.measure(p["stem"])
        corners = np.array(list(product(*zip(lo, hi))))
        points.extend(corners @ np.array(p["rot"]).reshape(3, 3).T + p["pos"])
    low, high = np.min(points, axis=0), np.max(points, axis=0)
    size = high - low
    return {"parts": len(flat), "bounds_ldu": [low.tolist(), high.tolist()], "size_ldu": size.tolist(),
            "size_mm": (size * .4).tolist(), "bounds_kind": "transformed part surface bounding boxes"}


def report_summary(report):
    result = {k: v for k, v in report.items() if k not in ("graph", "issues", "collision_pairs")}
    graph = report["graph"]
    result["graph"] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
        "components": len(graph["components"]), "component_sizes": [len(c) for c in graph["components"]]}
    result["issues"] = [{k: v for k, v in issue.items() if k != "leaf_ids"} for issue in report["issues"][:20]]
    result["issue_count"] = len(report["issues"])
    result["collision_pairs"] = report["collision_pairs"][:20]
    result["collision_pair_count"] = len(report["collision_pairs"])
    return result


def present(result):
    result = dict(result)
    if "validation" in result and isinstance(result["validation"], dict):
        result["validation"] = report_summary(result["validation"])
    if result.get("details"):
        details = dict(result["details"])
        for key in ("created_ids", "affected_ids", "invalidated_ids"):
            if key in details:
                details[key + "_count"] = len(details[key])
                details[key] = details[key][:50]
        result["details"] = details
    return result
