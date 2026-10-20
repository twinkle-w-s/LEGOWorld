"""Reuse one upstream model state and expose a focused design/review tool set."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PillowImage, ImageDraw

from lego_mcp import connectors, helpers, parts
from lego_mcp import server as engine
from lego_mcp.render import render_model_png

from legoworld.studio_io import load_studio_model, studio_mpd, write_io
from legoworld import catalog, precision
from legoworld.geometry import render_png
from legoworld.assets import ldraw_root

WORKSPACE = Path(os.environ.get("LEGOWORLD_WORKSPACE", Path.cwd())).resolve()
OUTPUTS = WORKSPACE / "outputs"
_PREVIEW_CACHE = (None, None)

INSTRUCTIONS = """You are the user's LEGO design agent. Use these tools to design, inspect,
render and revise a model, then export it for BrickLink Studio.
Start with create_model; search_parts/get_part_info expose the curated 60-part catalog.
Coordinates are LDU: 20 per stud, 8 per plate, 24 per brick; negative Y is UP.
Engine placements use the CENTER OF THE BOTTOM FACE. A brick at y=0 has its top
at y=-24. A plate stacked on it has its bottom at y=-24 and top at y=-32.
Use upright parts and quarter-turn Y rotations. Use get_connectors and attach_part
for exact stud/receiver alignment; slopes and jumpers do not have full top grids.
Use preview_placement before placing details, replace_part for local changes,
and transform_group for moving a subassembly atomically. Work in small batches. Grounded
parts can rest at y=0; use find_valid_placements/add_part_at_placement to attach.
Call review_model after a meaningful batch. It returns structured validation
and a FOUR-VIEW IMAGE as native MCP image content. Actually inspect that image.
Fix reported collisions, floating parts and grid errors before adding details.
Then revise proportions, silhouette, colors and details from the user's brief.
Save checkpoints before large edits. Keep a 100-300 part first design modest.
Use at most five visual-review revisions, or stop earlier when the user is happy.
If errors remain, report them and keep the draft. export_model only finalizes a
non-empty model passing stud/ground/grid and selected collision checks. BrickNet
convex penetration is geometry validation, not full physical stability or arbitrary
connector validation. Never treat missing collider data as verified.
Export through export_model, which corrects origins for Studio and writes .mpd
and .io from the SAME state. Do not call an unrelated exporter or rename files.
"""


def configure(workspace: Path) -> None:
    """Keep model outputs local and install the curated catalog and check adapter."""
    global WORKSPACE, OUTPUTS
    if os.environ.get("LEGOWORLD_RENDERER", "ldraw") not in ("ldraw", "boxes"):
        raise ValueError("LEGOWORLD_RENDERER must be ldraw or boxes")
    WORKSPACE = workspace.resolve()
    OUTPUTS = WORKSPACE / "outputs"
    os.environ["LEGO_MCP_RENDERS_DIR"] = str(OUTPUTS / "renders")
    os.environ["LEGO_MCP_INLINE_MODE"] = "none"
    engine.PROJECTS_DIR = WORKSPACE / ".cache" / "engine"
    engine.PART_INDEX = catalog.install()
    engine._LIBRARY_LOADED = True
    precision.install()


configure(WORKSPACE)
mcp = FastMCP("LEGOWorld", instructions=INSTRUCTIONS)

# The original MCP instance remains unused; these functions share its model.
for function in (
    engine.search_parts_tool,
    engine.list_colors,
    engine.list_parts,
    engine.remove_part,
    engine.move_part,
    engine.validate_model,
    engine.save_checkpoint,
    engine.restore_checkpoint,
    engine.set_current_subassembly,
    helpers.build_floor,
    helpers.build_room,
    helpers.build_wall_with_openings,
    helpers.build_stepped_gable_roof,
):
    mcp.add_tool(function)


@mcp.tool()
def create_model(name: str = "model") -> dict:
    """Start a new curated-part model; replaces the current in-memory model."""
    result = engine.create_model(name, include_manual=False)
    design_tools._PLACEMENTS.clear()
    result["workflow"] = "Build -> review_model (read image and errors) -> revise -> export_model."
    result["coordinates"] = "LDU, -Y up, bottom-face origins; 20/stud, 8/plate, 24/brick."
    return result


@mcp.tool()
def add_part(
    part_id: str, color: str, x: float, y: float, z: float,
    rotation: Literal["identity", "rot90y", "rot180y", "rot270y"] = "identity",
) -> dict:
    """Place an upright part. Reject collisions and unattached placements."""
    preview = design_tools.preview_placement(part_id, x, y, z, rotation, color)
    if not preview["ok"]:
        raise ValueError(f"Placement rejected: {preview}")
    return engine.add_part(part_id, color, x, y, z, rotation, strict=True)


@mcp.tool()
def recolor_part(instance_id: str, color: str) -> dict:
    """Change one existing part's color, retaining its geometry and connections."""
    instance = engine.STATE.parts[instance_id]
    instance.color = parts.resolve_color(color)
    return {"ok": True, "instance_id": instance_id, "color": instance.color}


@mcp.tool()
def rotate_part(
    instance_id: str,
    rotation: Literal["identity", "rot90y", "rot180y", "rot270y"],
) -> dict:
    """Rotate an existing part around Y; review the returned placement feedback."""
    return engine.rotate_part(instance_id, rotation)


def model_directory() -> Path:
    name = re.sub(r"[^\w-]+", "_", engine.STATE.name, flags=re.UNICODE).strip("_") or "model"
    directory = OUTPUTS / name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def four_view_png() -> bytes:
    """A fixed four-view contact sheet for the agent's visual review."""
    global _PREVIEW_CACHE
    key = (os.environ.get("LEGOWORLD_RENDERER", "ldraw"), str(ldraw_root()),
           tuple((p.part_id, p.color, p.x, p.y, p.z, engine.effective_matrix(p)) for p in engine.STATE.parts.values()))
    if _PREVIEW_CACHE[0] == key:
        return _PREVIEW_CACHE[1]
    sheet = PillowImage.new("RGB", (1200, 940), (245, 245, 248))
    draw = ImageDraw.Draw(sheet)
    for number, angle in enumerate((0, 90, 180, 270)):
        png = render_png(azimuth=angle) if os.environ.get("LEGOWORLD_RENDERER", "ldraw") == "ldraw" else render_model_png(
            engine.STATE.parts, engine.PART_INDEX, width=600, height=440,
            hidden_edges=False, view_angle=angle)
        x, y = (number % 2) * 600, (number // 2) * 470
        with PillowImage.open(io.BytesIO(png)) as view:
            sheet.paste(view, (x, y + 25))
        draw.text((x + 20, y + 8), f"View {number + 1} / azimuth {angle}", fill=(45, 50, 60))
    stream = io.BytesIO()
    sheet.save(stream, format="PNG")
    png = stream.getvalue()
    _PREVIEW_CACHE = (key, png)
    return png


@mcp.tool()
def review_model(note: str = "") -> list:
    """Validate and return native image content. Save this revision for comparison."""
    report = engine.validate_model()
    iterations = model_directory() / "iterations"
    iterations.mkdir(exist_ok=True)
    revision = max((int(p.name) for p in iterations.iterdir() if p.is_dir() and p.name.isdigit()), default=0) + 1
    directory = iterations / f"{revision:03d}"
    directory.mkdir()
    png = four_view_png()
    (directory / "preview.png").write_bytes(png)
    (directory / "model.mpd").write_text(studio_mpd(), encoding="utf-8")
    _write_json(directory / "validation.json", report)
    summary = {
        "revision": revision, "note": note, "validation": report,
        "preview": str(directory / "preview.png"),
        "next_action": "Inspect the returned image, fix errors, then improve the design or export.",
    }
    _write_json(directory / "review.json", summary)
    result = [json.dumps(summary, ensure_ascii=False), Image(data=png, format="png")]
    return result


@mcp.tool()
def export_model() -> dict:
    """Export a non-empty model passing the selected geometry and connection checks."""
    report = engine.validate_model()
    if not engine.STATE.parts or not report["valid"] or not report.get("structurally_sound", True):
        return {"ok": False, "reason": "Model is empty or has unresolved basic-check errors.", "validation": report}
    directory = model_directory()
    text = studio_mpd()
    (directory / "model.mpd").write_text(text, encoding="utf-8")
    write_io(directory / "model.io", text)
    (directory / "preview.png").write_bytes(four_view_png())
    _write_json(directory / "validation.json", report)
    result = {
        "ok": True, "checks": report["collision"],
        "renderer": os.environ.get("LEGOWORLD_RENDERER", "ldraw"),
        "parts": len(engine.STATE.parts),
        "mpd": str(directory / "model.mpd"), "io": str(directory / "model.io"),
        "preview": str(directory / "preview.png"),
        "validation": str(directory / "validation.json"),
    }
    _write_json(directory / "result.json", result)
    return result


@mcp.tool()
def load_model(path: str) -> dict:
    """Resume a basic LEGOWorld IO/MPD export. Unknown parts are rejected."""
    source = Path(path).expanduser().resolve()
    count = load_studio_model(source)
    return {"ok": True, "parts": count, "validation": engine.validate_model()}


from legoworld import design_tools
design_tools.register(mcp)
