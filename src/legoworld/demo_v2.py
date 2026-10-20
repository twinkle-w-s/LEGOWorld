"""Deterministic precision demo with an actual arched gateway and round towers."""

from legoworld import server
from legoworld.design_tools import measure_model, preview_placement, replace_part


def run_demo() -> dict:
    server.create_model("v2_castle_gate")
    add = server.add_part
    add("3811", "green", 0, 0, 0)
    for x in (-40, 40):
        add("3031", "light_bluish_gray", x, -4, 0)
    add("87079", "dark_bluish_gray", 0, -4, -60)
    for x in (-60, 60):
        for y in (-12, -36, -60):
            add("3941", "tan", x, y, 0)
        add("3942c", "red", x, -84, 0)
        add("6141", "yellow", x, -132, 0)
        add("4589", "red", x, -140, 0)
    for x in (-30, 30):
        for y in (-12, -36):
            add("3005", "tan", x, y, -30)
    add("3659", "tan", 0, -60, -30)
    add("3710", "dark_bluish_gray", 0, -84, -30)
    for x in (-10, 10):
        add("3040b", "red", x, -92, -20)
    add("3010", "tan", 0, -12, 30)
    for x in (-20, 20):
        add("3794b", "tan", x, -36, 30)
        add("6141", "yellow", x, -44, 30)
        add("4589", "red", x, -52, 30)
    for x in (-90, 90):
        for z in (-50, 50):
            add("6141", "bright_green", x, -4, z)
            add("98138", "yellow", x, -12, z)
    # Exercise non-mutating preflight and a validated local edit.
    blocked = preview_placement("3941", -60, -12, 0)
    assert not blocked["ok"] and blocked["collisions"]
    flower = next(p for p in server.engine.STATE.parts.values() if p.part_id == "98138")
    assert replace_part(flower.instance_id, "98138", "orange")["ok"]
    server.review_model("Actual arch opening, round towers, conical roofs, jumper details and round flowers.")
    result = server.export_model()
    result.update({"blocked_overlap": not blocked["ok"], "dimensions": measure_model(),
                   "new_part_types_used": sorted({p.part_id for p in server.engine.STATE.parts.values()
                                                 if server.catalog.RECORDS[p.part_id]["added_in_v2"]})})
    server._write_json(server.model_directory()/"demo.json", result)
    return result
