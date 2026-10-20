from zipfile import ZipFile

import pytest

from legoworld import server
from legoworld.studio_io import load_studio_model, studio_mpd, write_io


def test_mixed_brick_and_plate_have_correct_ldraw_top_origins(tmp_path):
    engine = server.engine
    engine.add_part("3001", "red", 0, 0, 0)
    engine.add_part("3020", "blue", 0, -24, 0)
    text = studio_mpd()
    native = engine.parse_ldr_text(text)
    assert [(p.part_id, p.y) for p in native] == [("3001", -24), ("3020", -32)]
    # The actual LDraw bodies extend downward from their top origins.
    assert native[1].y + 8 == native[0].y
    assert engine.STATE.parts["1"].y == 0  # export must not mutate the live scene
    path = tmp_path / "stack.io"
    write_io(path, text)
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert archive.read("model.ldr").decode("utf-8") == text
    assert load_studio_model(path) == 2
    assert [(p.part_id, p.y, p.color) for p in engine.STATE.parts.values()] == [
        ("3001", 0, 4), ("3020", -24, 1),
    ]
    assert engine.validate_model()["valid"] is True


@pytest.mark.parametrize("rotation", ["identity", "rot90y", "rot180y", "rot270y"])
def test_export_import_preserves_transforms_colors_and_subassemblies(tmp_path, rotation):
    engine = server.engine
    engine.set_current_subassembly("tower")
    engine.add_part("3004", "yellow", 40, 0, 20, rotation)
    before = next(iter(engine.STATE.parts.values()))
    expected = (before.part_id, before.color, before.x, before.y, before.z,
                engine.effective_matrix(before))
    path = tmp_path / "tower.mpd"
    path.write_text(studio_mpd(), encoding="utf-8")
    load_studio_model(path)
    after = next(iter(engine.STATE.parts.values()))
    assert (after.part_id, after.color, after.x, after.y, after.z,
            engine.effective_matrix(after)) == expected
    assert "tower" in after.subassembly
