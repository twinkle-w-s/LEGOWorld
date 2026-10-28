"""MCP interface to the same transactional hierarchy used by Python builds."""

from pathlib import Path
import asyncio
from functools import wraps
import json
import os

from mcp.server.fastmcp import FastMCP, Image

from legoworld import catalog
from legoworld import design_tools as inspection
from legoworld.document import entries
from legoworld.project import Project, write_json
from legoworld.backend import uid

INSTRUCTIONS = """LEGOWorld V3 uses BrickAgent and native LDraw coordinates: X/Z horizontal, -Y up,
20 LDU/stud, 8/plate, 24/brick. Part origins differ: prefer connectors over guessed heights.
Use get_model_tree to obtain the current revision and stable instance IDs. Every write requires
expected_revision. Python scripts inside the workspace implement build(**parameters) -> Assembly.
Use run_build_script for batches and reusable hierarchical components, then apply_edits for local
refinement. Local edits affect one occurrence through copy-on-write. Rebuilding a component
replaces its internal edits; external authored joins require expose_port names.
A batch must pass geometry and exact authored-contact checks. Stability is checked at export;
an unfinished draft is not a fully validated assembly. Missing assets never count as verified.
Use review_model and actually inspect its native four-view image, then revise proportions,
silhouette, colors and requested details. Checkpoints preserve the complete edited hierarchy.
Use export_model for basic Studio .io, hierarchical MPD, preview and V3 project snapshot.
The server calls no model API. Python scripts run as trusted local code in a disposable process,
with a timeout; this is fault isolation, not a security sandbox. Script side effects cannot be undone.
Use canonical part IDs returned by search. The full supported catalog is filtered by local assets.
"""

PROJECT = None


def configure(workspace):
    global PROJECT
    PROJECT = Project(workspace)


configure(Path(os.environ.get("LEGOWORLD_WORKSPACE", Path.cwd())))
mcp = FastMCP("LEGOWorld", instructions=INSTRUCTIONS)


def tool():
    """Keep the stdio event loop responsive while synchronous workers/files run."""
    def register(function):
        @wraps(function)
        async def call(**arguments):
            return await asyncio.to_thread(function, **arguments)
        mcp.add_tool(call)
        return function
    return register


@tool()
def create_model(name: str = "model", expected_revision: int = 0) -> dict:
    """Start a new project. Read get_model_tree first if this workspace already has a model."""
    return PROJECT.create(name, expected_revision)


@tool()
def run_build_script(path: str, expected_revision: int, parameters: dict | None = None,
                     mode: str = "replace_model", target_id: str = "root",
                     pose: dict | None = None, mount: dict | None = None,
                     timeout_seconds: float = 120) -> dict:
    """Run build(**parameters) -> Assembly. Modes: replace_model/add_component/replace_component.
    pose is a native local {t:[x,y,z],rot:[nine row-major values]}.
    mount={by:port_name,to:{node_id,port OR type,index},yaw/flip/slide/seat/orient...}.
    Component replacement discards edits inside its explicit target; other instances are retained.
    """
    return inspection.present(PROJECT.mutate("build", expected_revision, timeout_seconds,
        path=path, parameters=parameters or {}, mode=mode, target_id=target_id, pose=pose, mount=mount))


@tool()
def apply_edits(operations: list[dict], expected_revision: int) -> dict:
    """One transaction: add/instance/recolor/transform/replace/remove/connect/detach/attach/drop_port.
    add: part_id,parent_id?,pose?,color?,as?; instance: source_id,parent_id?,pose?,as?.
    transform: node_id OR node_ids,pose (world-space delta). recolor: node_id,color.
    connect/detach: a,b selectors. attach: node_id,by,to selectors plus native joint options.
    Selectors: {node_id,type,index} for parts or {node_id,port} for components.
    $alias references an earlier add/instance with as=alias in this batch.
    replace requires a connector_map for every referenced native connector if the part changes.
    Existing authored joins and exposed ports must be explicitly detached/dropped before deletion.
    """
    return inspection.present(PROJECT.mutate("edit", expected_revision, operations=operations))


@tool()
def add_part(part_id: str, color: str, expected_revision: int,
             pose: dict | None = None, parent_id: str = "root") -> dict:
    """Add at a native LDraw local pose; this is a one-operation apply_edits transaction."""
    return apply_edits([{"op": "add", "part_id": part_id, "color": color, "pose": pose, "parent_id": parent_id}], expected_revision)


@tool()
def attach_part(part_id: str, color: str, to: dict, by_type: str, by_index: int,
                expected_revision: int, options: dict | None = None) -> dict:
    """Add a part and attach by exact native connector placement in one transaction."""
    return apply_edits([{"op": "add", "part_id": part_id, "color": color, "as": "new"},
        {"op": "attach", "node_id": "$new", "by": {"node_id": "$new", "type": by_type, "index": by_index},
         "to": to, **(options or {})}], expected_revision)


@tool()
def recolor_part(node_id: str, color: str, expected_revision: int) -> dict:
    """Recolor one occurrence, retaining other copies of its shared definition."""
    return apply_edits([{"op": "recolor", "node_id": node_id, "color": color}], expected_revision)


@tool()
def search_parts(query: str = "", limit: int = 20, offset: int = 0, common_only: bool = False) -> dict:
    """Rank asset-complete BrickAgent parts; common_only restricts the V2 common selection."""
    return catalog.search(query, limit, offset, common_only)


@tool()
def get_part_info(part_id: str) -> dict:
    """Native bounds, names, typed connectors and recursive asset availability."""
    return catalog.info(part_id)


@tool()
def get_connectors(part_id: str | None = None, node_id: str | None = None,
                   offset: int = 0, limit: int = 100) -> dict:
    """Read part-local connectors or an instance's world connectors/component ports."""
    with PROJECT.lock:
        return inspection.get_connectors(PROJECT.document, part_id, node_id, offset, limit)


@tool()
def get_model_tree(target_id: str = "root", depth: int = 1, offset: int = 0, limit: int = 100) -> dict:
    """Get the current revision, stable instance IDs, shared definitions, poses and port names."""
    return PROJECT.tree(target_id, depth, offset, limit)


@tool()
def get_connection_graph(target_id: str = "root", offset: int = 0, limit: int = 100) -> dict:
    """Inferred native graph edges touching this component, with authored joins separately recorded."""
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("Use limit 1..500 and nonnegative offset")
    with PROJECT.lock:
        known = entries(PROJECT.document)
        if target_id not in known:
            raise KeyError(target_id)
        graph = PROJECT.validate()["graph"]
        selected = {n for n in graph["nodes"] if n == target_id or n.startswith(target_id + "/")}
        edges = [e for e in graph["edges"] if e["a"] in selected or e["b"] in selected]
        return {"revision": PROJECT.revision, "nodes": sorted(selected), "edges": edges[offset:offset+limit],
                "edge_count": len(edges), "has_more": offset+limit < len(edges),
                "components": [[n for n in c if n in selected] for c in graph["components"] if selected.intersection(c)],
                "authored_joins": PROJECT.document["definitions"][known[target_id]["definition"]]["joins"]
                    if known[target_id]["assembly"] else []}


@tool()
def inspect_part(node_id: str) -> dict:
    """Inspect one part or component, its world connectors and current validation summary."""
    with PROJECT.lock:
        return {"revision": PROJECT.revision, "node": entries(PROJECT.document)[node_id],
                "connectors": get_connectors(node_id=node_id),
                "validation": inspection.report_summary(PROJECT.validate())}


@tool()
def measure_model(node_ids: list[str] | None = None) -> dict:
    """Measure native transformed surface bounds, including studs; LDU and millimeters."""
    with PROJECT.lock:
        return {"revision": PROJECT.revision, **inspection.measure(PROJECT.document, node_ids)}


@tool()
def preview_placement(part_id: str, pose: dict, color: str = "light bluish gray",
                      parent_id: str = "root") -> dict:
    """Read-only native geometry/contact preflight; does not commit or require grounding."""
    with PROJECT.lock:
        result = PROJECT.worker("edit", operations=[{"op": "add", "part_id": part_id,
                            "color": color, "pose": pose, "parent_id": parent_id}])
        result.pop("document", None)
        result["revision"] = PROJECT.revision
        return inspection.present(result)


@tool()
def validate_model(stability: bool = False, candidate_id: str | None = None) -> dict:
    """Check batch geometry/contacts or include full native stability. Never equate these stages."""
    return inspection.report_summary(PROJECT.validate(stability, candidate_id))


@tool()
def render_view(azimuth: float = 35, elevation: float = 28,
                node_ids: list[str] | None = None, candidate_id: str | None = None) -> list:
    """Native MCP image of the model or selected components, including a rejected candidate."""
    with PROJECT.lock:
        return [json.dumps({"revision": PROJECT.revision, "candidate_id": candidate_id}),
                Image(data=PROJECT.render(candidate_id, azimuth=azimuth, elevation=elevation, node_ids=node_ids), format="png")]


@tool()
def review_model(note: str = "", candidate_id: str | None = None, stability: bool = False) -> list:
    """Save a visual review and return a native four-view image plus a bounded check report."""
    with PROJECT.lock:
        doc = PROJECT.selected_document(candidate_id)
        report = PROJECT.validate(stability, candidate_id)
        png = PROJECT.render(candidate_id, four_views=True)
        directory = PROJECT.outputs / "reviews" / uid()
        directory.mkdir(parents=True)
        (directory / "preview.png").write_bytes(png)
        write_json(directory / "project.json", doc)
        write_json(directory / "validation.json", report)
        summary = {"revision": doc["revision"], "candidate_id": candidate_id, "note": note,
                   "validation": inspection.report_summary(report), "directory": str(directory)}
        write_json(directory / "review.json", summary)
        return [json.dumps(summary, ensure_ascii=False), Image(data=png, format="png")]


@tool()
def export_model() -> dict:
    """Export only after native collision, exact authored-contact and full stability checks."""
    return inspection.present(PROJECT.export())


@tool()
def load_model(path: str, expected_revision: int) -> dict:
    """Load V3 project JSON or standard MPD/LDR/basic IO; import is transactional."""
    return inspection.present(PROJECT.mutate("import", expected_revision, path=path))


@tool()
def save_checkpoint() -> dict:
    """Save the complete current hierarchy, including MCP changes made after a script build."""
    return PROJECT.save_checkpoint()


@tool()
def restore_checkpoint(checkpoint_id: str, expected_revision: int) -> dict:
    """Restore a complete snapshot as a new revision; old revision numbers are never reused."""
    return inspection.present(PROJECT.restore_checkpoint(checkpoint_id, expected_revision))
