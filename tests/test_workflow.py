import io
import json

import pytest

from mcp.server.fastmcp import Image
from PIL import Image as PillowImage

from legoworld import server


def test_collision_is_detected_repaired_and_then_exported():
    engine = server.engine
    engine.add_part("3001", "red", 0, 0, 0)
    duplicate = engine.add_part("3001", "blue", 0, 0, 0)
    assert engine.validate_model()["summary"]["collisions"] == 1
    assert server.export_model()["ok"] is False
    engine.remove_part(duplicate["instance_id"])
    assert engine.validate_model()["valid"] is True
    result = server.export_model()
    assert result["ok"] is True
    assert result["parts"] == 1


def test_empty_and_floating_models_are_not_finalized():
    assert server.export_model()["ok"] is False
    server.engine.add_part("3001", "red", 0, -100, 0)
    assert server.export_model()["ok"] is False
    assert not (server.model_directory() / "model.io").exists()


def test_grounded_but_disconnected_parts_are_not_finalized():
    server.engine.add_part("3001", "red", 0, 0, 0)
    server.engine.add_part("3001", "blue", 200, 0, 0)
    result = server.export_model()
    assert result["ok"] is False
    assert result["validation"]["summary"]["rigid_bodies"] == 2


def test_review_returns_real_image_and_saves_distinct_revisions():
    server.engine.add_part("3001", "red", 0, 0, 0)
    first = server.review_model("Red version")
    image = next(block for block in first if isinstance(block, Image))
    with PillowImage.open(io.BytesIO(image.data)) as picture:
        assert picture.size == (1200, 940)
    server.recolor_part("1", "blue")
    second = server.review_model("Blue version")
    assert json.loads(first[0])["revision"] == 1
    assert json.loads(second[0])["revision"] == 2
    assert first[1].data != second[1].data
    assert (server.model_directory() / "iterations" / "001" / "model.mpd").is_file()


def test_strict_placement_rejects_overlap_and_allows_attachment():
    server.add_part("3001", "red", 0, 0, 0)
    with pytest.raises(ValueError):
        server.add_part("3001", "blue", 0, 0, 0)
    server.add_part("3001", "blue", 0, -24, 0)
    assert server.engine.validate_model()["valid"] is True


def test_offline_demo_exercises_conflict_and_repair():
    from legoworld.demo import run_demo
    result = run_demo()
    assert result["ok"] is True, result
    assert result["collision_detected"] is True
    assert result["repair_passed"] is True
