from copy import deepcopy
import importlib.util

import numpy as np
import pytest

from legoworld import server
from legoworld.assets import collider_root, ldraw_root
from legoworld.catalog import RECORDS
from legoworld import design_tools as tools
from legoworld.geometry import mesh, render_png
from legoworld.precision import collision_report, ldraw_matrix
from legoworld.studio_io import studio_mpd, load_studio_model


@pytest.fixture(autouse=True)
def precision_backend(monkeypatch):
    if (importlib.util.find_spec("pybullet") is None or
            not (collider_root()/"cvx/3001.cvx.obj").is_file() or
            not (ldraw_root()/"parts/3001.dat").is_file()):
        pytest.skip("Install .[precision] and run legoworld fetch-assets for real-asset integration checks")
    monkeypatch.setenv("LEGOWORLD_COLLISION", "bricknet")
    monkeypatch.setenv("LEGOWORLD_RENDERER", "ldraw")


def test_round_parts_clear_despite_overlapping_boxes_and_true_overlap_rejected():
    server.add_part("3941", "red", 0, 0, 0)
    server.add_part("3941", "blue", 30, 0, 30)
    a, b = list(server.engine.STATE.parts.values())
    assert server.engine.aabbs_overlap(server.engine.part_aabb_world(a, server.engine.PART_INDEX[a.part_id]),
                                      server.engine.part_aabb_world(b, server.engine.PART_INDEX[b.part_id]))
    assert collision_report()["verified"] and collision_report()["pairs"] == []
    with pytest.raises(ValueError):
        server.add_part("3941", "yellow", 0, 0, 0)
    assert len(server.engine.STATE.parts) == 2


def test_missing_colliders_block_finalization(monkeypatch, tmp_path):
    server.add_part("3001", "red", 0, 0, 0)
    monkeypatch.setenv("BRICKNET_DATA", str(tmp_path/"missing"))
    report = server.engine.validate_model()
    assert not report["valid"] and not report["collision"]["verified"]
    assert report["collision"]["missing"] == ["1"]
    assert server.export_model()["ok"] is False


def test_real_connector_attachment_and_preview_dont_guess_full_top_grid():
    base = server.add_part("3039", "red", 0, 0, 0)["instance_id"]
    points = tools.get_connectors("3039", base)["connectors"]
    assert len([p for p in points if p["type"] == "stud_top"]) == 2
    assert points[0]["local"] == (-10, -24, 10)
    before = deepcopy(server.engine.STATE)
    assert tools.preview_placement("3005", -10, -24, 10)["ok"]
    assert server.engine.STATE == before
    receiver = next(p["index"] for p in tools.get_connectors("3005")["connectors"] if p["type"] == "stud_receiver_bottom")
    assert tools.attach_part(base, 0, "3005", receiver, "yellow")["ok"]
    assert server.engine.validate_model()["valid"]
    assert not tools.preview_placement("3005", -10, -24, -10)["ok"]


def test_all_added_parts_attach_to_real_base_studs():
    for pid, record in RECORDS.items():
        if not record["added_in_v2"]:
            continue
        server.create_model("attach_"+pid)
        server.add_part("3031", "light_bluish_gray", 0, 0, 0)
        receiver = next(p["index"] for p in tools.get_connectors(pid)["connectors"]
                        if p["type"] == "stud_receiver_bottom")
        attached = tools.attach_part("1", 0, pid, receiver, "red")
        assert attached["ok"], (pid, attached)
        assert server.engine.validate_model()["valid"], pid


def test_replace_and_group_transform_rollback_all_model_state():
    server.add_part("3001", "red", 0, 0, 0)
    server.add_part("3020", "blue", 0, -24, 0)
    before = deepcopy(server.engine.STATE)
    assert tools.replace_part("1", "3020")["rolled_back"]
    assert server.engine.STATE == before
    assert tools.transform_group(["1", "2"], dx=20, quarter_turns=1)["ok"]
    assert server.engine.STATE.parts["1"].x == 20
    before = deepcopy(server.engine.STATE)
    assert tools.transform_group(["1", "2"], dy=-100)["rolled_back"]
    assert server.engine.STATE == before


@pytest.mark.parametrize("rotation", tools.ROTATIONS)
def test_all_28_new_parts_geometry_colliders_and_origin_round_trip(rotation, tmp_path):
    assert len(RECORDS) == 60
    additions = {p: r for p, r in RECORDS.items() if r["added_in_v2"]}
    assert len(additions) == 28
    for index, (pid, record) in enumerate(additions.items()):
        assert len(mesh(pid+".dat")[0]) > 0
        assert (collider_root()/"cvx"/(record["collider"]+".cvx.obj")).is_file()
        server.engine.add_part(pid, "red", index*300, 0, 0, rotation, strict=True)
    poses = {p.part_id: ldraw_matrix(p) for p in server.engine.STATE.parts.values()}
    path = tmp_path/"new-parts.mpd"
    path.write_text(studio_mpd(), encoding="utf-8")
    load_studio_model(path)
    for p in server.engine.STATE.parts.values():
        np.testing.assert_allclose(ldraw_matrix(p), poses[p.part_id], atol=1e-5)


def test_render_uses_actual_slope_geometry_and_camera():
    server.add_part("3039", "red", 0, 0, 0)
    slope = render_png(90, 0, 300, 250)
    assert tools.replace_part("1", "3003")["ok"]
    brick = render_png(90, 0, 300, 250)
    assert slope != brick
    assert brick != render_png(35, 28, 300, 250)


def test_coincident_compound_baseplates_are_detected_without_native_contact_overflow():
    server.engine.add_part("3811", "green", 0, 0, 0)
    server.engine.add_part("3811", "blue", 0, 0, 0)
    assert collision_report()["pairs"] == [["1", "2"]]


def test_unsupported_import_orientation_preserves_current_model(tmp_path):
    server.add_part("3001", "red", 0, 0, 0)
    before = deepcopy(server.engine.STATE)
    path = tmp_path/"tilted.ldr"
    path.write_text("0 Unsupported pose\n1 4 0 0 0 1 0 0 0 0 -1 0 1 0 3001.dat\n", encoding="utf-8")
    with pytest.raises(ValueError, match="upright"):
        load_studio_model(path)
    assert server.engine.STATE == before
