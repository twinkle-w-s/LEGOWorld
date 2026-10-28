"""Native BrickAgent checks with stable IDs and fail-closed asset preflights."""

import io
from contextlib import redirect_stdout
from time import perf_counter

from legoworld.backend import b, unpack, authored_contact_errors
from legoworld.document import flat_records
from legoworld.catalog import asset_status


def validate_document(doc, stability=False):
    started = perf_counter()
    model = unpack(doc)
    flat = flat_records(doc, model)
    ids = [p["id"] for p in flat]
    issues = []
    checked = {}
    for stem in sorted({p["stem"] for p in flat}):
        status = asset_status(stem, checked)
        if not status["available"]:
            issues.append({"type": "missing_assets", **status})
    poses = {}
    for p in flat:
        key = (p["stem"], tuple(p["pos"]), tuple(p["rot"]))
        if key in poses:
            issues.append({"type": "duplicate_pose", "instance_a": poses[key], "instance_b": p["id"]})
        poses[key] = p["id"]
    report = {"backend": "brickagent/bricknet", "tolerance_ldu": 1.0, "parts": len(flat),
        "revision": doc["revision"], "geometry_valid": False, "connections_valid": False,
        "stability": {"checked": False, "stable": None, "max_displacement_ldu": 3.0},
        "exportable": False, "batch_valid": False, "issues": issues,
        "graph": {"nodes": ids, "edges": [], "components": []}, "collision_pairs": []}
    if issues:
        report["seconds"] = perf_counter() - started
        return report
    graph = b.connections(model)
    report["graph"] = {"nodes": ids,
        "edges": [{"a": ids[int(e["a"])], "b": ids[int(e["b"])],
                   **{k: e[k].tolist() for k in graph.edges.dtype.names if k not in ("a", "b")}}
                  for e in graph.edges],
        "components": [[ids[i] for i in component] for component in graph.components]}
    pairs = b.clashes(model)
    report["collision_pairs"] = [[ids[a], ids[c]] for a, c in pairs]
    report["geometry_valid"] = not pairs
    contact_errors = authored_contact_errors(model, graph)
    report["connections_valid"] = not contact_errors
    issues.extend({"type": "authored_contact", "message": e} for e in contact_errors)
    for a, c in pairs:
        issues.append({"type": "collision", "instance_a": ids[a], "instance_b": ids[c]})
    try:
        with redirect_stdout(io.StringIO()):
            b.check(model, stability=False)
        report["batch_valid"] = True
    except ValueError as error:
        issues.append({"type": "native_check", "message": str(error), "leaf_ids": ids})
    if stability and report["batch_valid"] and flat:
        report["stability"]["checked"] = True
        try:
            with redirect_stdout(io.StringIO()):
                b.check(model)
            report["stability"]["stable"] = True
        except ValueError as error:
            report["stability"]["stable"] = False
            issues.append({"type": "stability", "message": str(error), "leaf_ids": ids})
    if not flat and stability:
        issues.append({"type": "empty_model"})
    report["exportable"] = bool(flat) and report["batch_valid"] and report["stability"]["stable"] is True
    report["seconds"] = perf_counter() - started
    return report
