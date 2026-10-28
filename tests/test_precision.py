from copy import deepcopy

import numpy as np
import pytest

from legoworld.backend import b, pack, unpack
from legoworld.document import entries, flat_records
from legoworld.editing import apply_operations
from legoworld.precision import validate_document


def assembly(kind):
    specs = {"stud": ("3001", "3005", "stud", "hole"),
             "side": ("87087", "6141", "open", "tube"),
             "pin": ("technic beam 5", "2780", "socket", "pin"),
             "axle": ("technic beam 5", "3705", "socket", "axle"),
             "hinge": ("2926", "6014b", "hinge", "hinge"),
             "ball": ("22890", "14418", "ball", "ball")}
    base, top, a, c = specs[kind]
    model = b.Assembly(kind)
    lower = model.add(base, color="red")
    options = {"orient": b.spin(b.UP, 150)} if kind == "ball" else {}
    model.attach(top, to=getattr(lower, a)[0], by=(c, 0), color="yellow", **options)
    return model


@pytest.mark.parametrize("kind", ("stud", "side", "pin", "axle", "hinge", "ball"))
def test_native_connector_and_collision_parity(real_assets, kind):
    model = assembly(kind)
    b.check(model, stability=False)
    doc = pack(model)
    report = validate_document(doc)
    assert report["batch_valid"] and not report["exportable"]
    assert len(report["graph"]["edges"]) == len(b.connections(model).edges)
    assert report["collision_pairs"] == list(b.clashes(model)) == []
    assert len(b.attachments(unpack(doc))) == 1
    assert not report["stability"]["checked"]


def test_nested_shared_roundtrip_inherits_poses_colors_and_authored_joins(real_assets):
    unit = assembly("stud")
    middle = b.Assembly("middle")
    middle.add(unit, pose=b.move(20, 0, 0))
    scene = b.Assembly("scene")
    scene.add(middle, pose=b.spin(b.UP, 90), color="blue")
    scene.add(middle, pose=b.move(120, 0, 0))
    doc = pack(scene)
    restored = unpack(doc)
    assert restored.children[0].what is restored.children[1].what
    assert b.ldraw(restored) == b.ldraw(scene)
    actual, expected = flat_records(doc), b.parts(scene)
    assert len(actual) == len(expected) == 4
    for a, e in zip(actual, expected):
        assert (a["stem"], a["color"]) == (e.stem, e.color)
        np.testing.assert_allclose(a["pos"], e.pos)
        np.testing.assert_allclose(a["rot"], e.rot)
    assert validate_document(doc)["batch_valid"]


def test_copy_on_write_keeps_other_instances_and_connectors(real_assets):
    unit = assembly("stud")
    scene = b.Assembly("scene")
    scene.add(unit)
    scene.add(unit, pose=b.move(120, 0, 0))
    doc = pack(scene)
    leaves = flat_records(doc)
    original = deepcopy(doc)
    edited, _ = apply_operations(doc, [{"op": "recolor", "node_id": leaves[1]["id"], "color": "green"}])
    assert doc == original
    colors = [p["color"] for p in flat_records(edited)]
    assert colors[1] == b.color("green") and colors[3] == b.color("yellow")
    assert unpack(edited).children[0].what is not unpack(edited).children[1].what
    assert validate_document(edited)["batch_valid"]


def test_near_miss_graph_does_not_satisfy_exact_authored_join(real_assets):
    doc = pack(assembly("stud"))
    leaf = flat_records(doc)[1]["id"]
    changed, _ = apply_operations(doc, [{"op": "transform", "node_id": leaf, "pose": {"t": [0, -.01, 0]}}])
    report = validate_document(changed)
    assert report["geometry_valid"] and len(report["graph"]["edges"]) == 1
    assert not report["connections_valid"] and not report["batch_valid"]
    assert "Non-exact connection" in report["issues"][-1]["message"]


def test_explicit_detach_then_move_preserves_other_authored_joins(real_assets):
    doc = pack(assembly("stud"))
    a, c = [p["id"] for p in flat_records(doc)]
    edited, _ = apply_operations(doc, [
        {"op": "detach", "a": {"node_id": a, "type": "stud", "index": 0},
         "b": {"node_id": c, "type": "hole", "index": 0}},
        {"op": "transform", "node_id": c, "pose": {"t": [100, 0, 0]}}])
    assert validate_document(edited)["batch_valid"]
    assert len(b.attachments(unpack(edited))) == 0


def test_duplicate_compound_baseplate_preflight_avoids_native_query(real_assets, monkeypatch):
    model = b.Assembly("duplicates")
    model.add("3811")
    model.add("3811")
    monkeypatch.setattr(b, "clashes", lambda _: pytest.fail("Duplicate poses must be caught before Bullet"))
    report = validate_document(pack(model))
    assert not report["batch_valid"]
    assert report["issues"][0]["type"] == "duplicate_pose"


def test_round_solids_clear_when_boxes_overlap_and_true_collision_matches_native(real_assets):
    model = b.Assembly("round")
    model.add("3941")
    model.add("3941", pose=b.move(30, 0, 30))
    doc = pack(model)
    assert validate_document(doc)["batch_valid"]
    ids = [p["id"] for p in flat_records(doc)]
    overlap, _ = apply_operations(doc, [{"op": "transform", "node_id": ids[1], "pose": {"t": [-20, 0, -20]}}])
    native = b.clashes(unpack(overlap))
    report = validate_document(overlap)
    assert native and len(report["collision_pairs"]) == len(native)
    assert not report["batch_valid"]


def test_missing_assets_never_pass(real_assets, monkeypatch, tmp_path):
    model = b.Assembly("missing")
    model.add("3001")
    monkeypatch.setenv("BRICKNET_DATA", str(tmp_path / "not-installed"))
    report = validate_document(pack(model), True)
    assert not report["geometry_valid"] and not report["exportable"]
    assert report["issues"][0]["type"] == "missing_assets"


def test_final_stability_allows_multiple_bodies_and_rejects_floating_body(real_assets):
    model = b.Assembly("scene")
    model.add("3001")
    model.add("3005", pose=b.move(100, 0, 0))
    # Native origins differ by height: put the smaller brick's bottom on the same floor.
    assert validate_document(pack(model), True)["exportable"]
    model = b.Assembly("floating")
    model.add("3001")
    model.add("3005", pose=b.move(100, -80, 0))
    doc = pack(model)
    assert validate_document(doc)["batch_valid"]
    final = validate_document(doc, True)
    assert final["stability"]["checked"] and final["stability"]["stable"] is False
    assert not final["exportable"]
