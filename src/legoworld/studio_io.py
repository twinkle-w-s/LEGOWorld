"""Native LDraw hierarchy import and basic Studio container export."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from bricknet.data import load_aliases
from legoworld.backend import b


def write_io(path: Path, mpd: str):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("model.ldr", mpd.encode("utf-8"))


def read_model(path):
    path = Path(path)
    if path.suffix.lower() == ".io":
        with ZipFile(path) as archive:
            if "modelv2.ldr" in archive.namelist():
                raise ValueError("Use a Studio-exported MPD for modelv2 projects")
            text = archive.read("model.ldr").decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    return parse_mpd(text, path.stem)


def parse_mpd(text, name="imported"):
    definitions, current, first = {}, None, None
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) >= 3 and tokens[:2] == ["0", "FILE"]:
            current = " ".join(tokens[2:]).casefold()
            if current in definitions:
                raise ValueError("Repeated MPD file definition")
            definitions[current] = []
            first = first or current
        elif tokens and tokens[0] == "1":
            if current is None:
                current = first = "main.ldr"
                definitions[current] = []
            if len(tokens) < 15:
                raise ValueError("Incomplete LDraw type-1 line")
            definitions[current].append(tokens)
    if not definitions:
        raise ValueError("No model instances found")
    memo, pending = {}, set()
    aliases = load_aliases()

    def build(key):
        if key in pending:
            raise ValueError("Cyclic MPD references")
        if key in memo:
            return memo[key]
        pending.add(key)
        model = b.Assembly(name if key == first else key.removesuffix(".ldr"))
        for tokens in definitions[key]:
            ref = " ".join(tokens[14:]).replace("\\", "/").casefold()
            values = np.array(tokens[2:14], dtype=float)
            matrix = np.eye(4)
            matrix[:3, :3] = values[3:].reshape(3, 3)
            matrix[:3, 3] = values[:3]
            if ref in definitions:
                what = build(ref)
            else:
                stem = ref.removesuffix(".dat")
                if stem in aliases:
                    stem, wrapper = aliases[stem]
                    matrix = matrix @ wrapper
                what = b.resolve(stem)
            model.add(what, pose=b.Pose(tuple(matrix[:3, :3].ravel()), tuple(matrix[:3, 3])), color=int(tokens[1]))
        pending.remove(key)
        memo[key] = model
        return model
    return build(first)
