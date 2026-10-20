"""An offline tool-chain check, deliberately not presented as LLM generation."""

from legoworld import server


def run_demo() -> dict:
    """Build a small house, demonstrate a conflict/repair, review and export."""
    engine, helpers = server.engine, server.helpers
    engine.create_model("demo_house")
    engine.add_part("3811", "green", 0, 0, 0, strict=True)
    helpers.build_floor(-160, -120, 160, 120, y=-4, color="green", part_id="3031")
    helpers.build_room(
        -100, -60, 100, 60, height_rows=5, base_y=-12, color="tan",
        openings={"south": [{"center": 100, "width": 40, "bottom_row": 0,
                              "height_rows": 3, "type": "door"}]},
    )
    helpers.build_stepped_gable_roof(
        -120, -80, 120, 80, eave_y=-132, ridge_axis="z", color="red",
    )
    before = engine.validate_model()
    if not before["valid"] or not before.get("structurally_sound", True):
        return {"ok": False, "phase": "build", "validation": before}
    server.review_model("Initial house; deterministic offline demo.")
    # Deliberately duplicate a part through the engine, allowing the validator
    # to expose an error that an agent would have to diagnose and repair.
    first = next(iter(engine.STATE.parts.values()))
    duplicate = engine.add_part(first.part_id, "blue", first.x, first.y, first.z)
    conflict = engine.validate_model()
    server.review_model("Deliberate overlap to exercise diagnostic feedback.")
    engine.remove_part(duplicate["instance_id"])
    repaired = engine.validate_model()
    server.review_model("Removed the colliding duplicate; green ground and red roof retained.")
    result = server.export_model()
    result["collision_detected"] = conflict["summary"]["collisions"] > 0
    result["repair_passed"] = repaired["valid"] and repaired.get("structurally_sound", True)
    server._write_json(server.model_directory() / "demo.json", result)
    return result
