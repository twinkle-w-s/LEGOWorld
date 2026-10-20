"""Translate the engine's bottom-face origins to standard LDraw top origins."""

from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lego_mcp import server as engine


def studio_mpd() -> str:
    """Export common upright parts without shifting plates into adjacent bricks."""
    state = deepcopy(engine.STATE)
    for instance in state.parts.values():
        part = engine.PART_INDEX[instance.part_id]
        offset = engine.matrix_apply(engine.effective_matrix(instance), (0, -part.height, 0))
        instance.x += offset[0]
        instance.y += offset[1]
        instance.z += offset[2]
    return engine.emit_mpd(state)


def write_io(path: Path, mpd: str) -> None:
    """Write a new basic Studio project, using its standard LDraw fallback entry.

    This creates a new model, not a round-trip editor for Studio page layouts,
    thumbnails, custom parts or modelv2 metadata.
    """
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("model.ldr", mpd.encode("utf-8"))


def load_studio_model(path: Path) -> int:
    """Load an exported basic model, translating its origins back to the engine."""
    if path.suffix.lower() == ".io":
        with ZipFile(path) as archive:
            if "modelv2.ldr" in archive.namelist():
                raise ValueError("This MVP imports its own basic .io exports; use a Studio-exported MPD for other projects.")
            text = archive.read("model.ldr").decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    instances = engine.parse_ldr_text(text)
    if not instances:
        raise ValueError("No parts found in the model.")
    for instance in instances:
        if instance.part_id not in engine.PART_INDEX:
            raise ValueError(f"Part {instance.part_id} is outside the MVP catalog.")
        part = engine.PART_INDEX[instance.part_id]
        offset = engine.matrix_apply(engine.effective_matrix(instance), (0, part.height, 0))
        instance.x += offset[0]
        instance.y += offset[1]
        instance.z += offset[2]
    engine.create_model(path.stem)
    for instance in instances:
        instance.instance_id = engine.STATE.new_id()
        engine.STATE.parts[instance.instance_id] = instance
        engine.STATE.built.add(instance.instance_id)
    return len(instances)
