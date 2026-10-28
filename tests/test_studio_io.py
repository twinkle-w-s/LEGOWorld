import json
from zipfile import ZipFile

import numpy as np
import pytest

from legoworld.backend import b, pack, unpack
from legoworld.build import expose_port
from legoworld.studio_io import parse_mpd, read_model, write_io


def poses(model):
    return [(p.stem, p.color, np.array(p.pose.matrix)) for p in b.parts(model)]


def test_native_hierarchy_io_and_json_round_trip(tmp_path):
    component = b.Assembly("roof")
    part = component.add("3039", color="red")
    expose_port(component, "bottom", part.hole[0])
    model = b.Assembly("scene")
    model.add(component, pose=b.spin((1, 0, 0), 90), color="blue")
    model.add(component, pose=b.move(100, 20, -10) @ b.spin(b.UP, 37))
    text = b.ldraw(model)
    path = tmp_path / "model.io"
    write_io(path, text)
    with ZipFile(path) as archive:
        assert archive.namelist() == ["model.ldr"]
    imported = read_model(path)
    for original, actual in zip(poses(model), poses(imported)):
        assert original[:2] == actual[:2]
        np.testing.assert_allclose(original[2], actual[2], atol=1e-10)
    assert imported.children[0].what is imported.children[1].what
    restored = unpack(json.loads(json.dumps(pack(model))))
    assert restored.children[0].what is restored.children[1].what
    assert b.ldraw(restored) == text
    # MPD has geometry only. Project JSON additionally preserves the ports.
    assert getattr(restored.children[0].what, "_legoworld_ports")["bottom"].type == "hole"


def test_alias_import_applies_native_wrapper():
    from bricknet.data import load_aliases
    stem = "3023"
    canonical, wrapper = load_aliases()[stem]
    imported = parse_mpd("0 old\n1 4 10 20 30 1 0 0 0 1 0 0 0 1 3023.dat\n")
    placed = b.parts(imported)[0]
    assert placed.stem == canonical
    np.testing.assert_allclose(placed.pose.matrix, b.move(10, 20, 30).matrix @ wrapper)


@pytest.mark.parametrize("text", [
    "0 FILE a.ldr\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 a.ldr",
    "0 FILE a.ldr\n0 FILE A.ldr\n",
    "0 bad\n1 4 0 0 0 2 0 0 0 1 0 0 0 1 3001.dat"])
def test_bad_imports_rejected(text):
    with pytest.raises((ValueError, KeyError)):
        parse_mpd(text)
