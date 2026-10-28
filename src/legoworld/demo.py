"""Deterministic hybrid demonstration; no language-model API is called."""

from pathlib import Path
from time import perf_counter

from legoworld.backend import uid
from legoworld.document import flat_records
from legoworld.project import write_json


def run_demo(project):
    source = Path(__file__).resolve().parents[2] / "examples/builds/castle_v3.py"
    if not source.is_file():
        raise FileNotFoundError("The demo requires a source checkout with examples/builds/castle_v3.py")
    script = project.outputs / "demo_scripts" / (uid() + ".py")
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    started = perf_counter()
    built = project.mutate("build", project.revision, path=str(script), parameters={},
                          mode="replace_model", target_id="root")
    if not built["ok"]:
        return built
    lamp = next(p for p in flat_records(project.document) if p["stem"] == "6141")
    edited = project.mutate("edit", project.revision, operations=[
        {"op": "recolor", "node_id": lamp["id"], "color": "orange"}])
    if not edited["ok"]:
        return edited
    result = project.export()
    result.update({"construction_requests": 1, "refinement_requests": 1,
                   "seconds": perf_counter()-started, "deterministic_demo": True,
                   "definitions": len(project.document["definitions"])})
    if result["ok"]:
        write_json(Path(result["project"]).parent / "demo.json", result)
    return result
