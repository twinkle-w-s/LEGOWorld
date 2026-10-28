"""Compare the transaction API behind MCP, excluding client/transport overhead."""

import json
from pathlib import Path
from time import perf_counter

from legoworld.document import flat_records
from legoworld.project import Project, write_json


def geometry(doc):
    return [(p["stem"], p["color"], p["pos"], p["rot"]) for p in flat_records(doc)]


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/benchmark_v3"
    workspace = output / "hybrid"
    workspace.mkdir(parents=True, exist_ok=True)
    script = workspace / "build.py"
    script.write_text((root / "examples/builds/castle_v3.py").read_text(encoding="utf-8"), encoding="utf-8")
    hybrid = Project(workspace)
    hybrid.create("hybrid", hybrid.revision)
    started = perf_counter()
    built = hybrid.mutate("build", hybrid.revision, path=str(script), parameters={}, mode="replace_model", target_id="root")
    if not built["ok"]:
        raise RuntimeError(built)
    hybrid_seconds = perf_counter() - started
    expected = geometry(hybrid.document)
    baseline = Project(output / "individual")
    baseline.create("individual", baseline.revision)
    validation_seconds = 0
    started = perf_counter()
    for i, (stem, color, position, rotation) in enumerate(expected, 1):
        result = baseline.mutate("edit", baseline.revision, operations=[
            {"op": "add", "part_id": stem, "color": color, "pose": {"t": position, "rot": rotation}}])
        if not result["ok"]:
            raise RuntimeError(result)
        validation_seconds += result["validation"]["seconds"]
        if i % 25 == 0:
            print(f"individual {i}/{len(expected)}", flush=True)
    baseline_seconds = perf_counter() - started
    assert geometry(baseline.document) == expected
    hybrid_final, baseline_final = hybrid.validate(True), baseline.validate(True)
    assert hybrid_final["exportable"] and baseline_final["exportable"]
    report = {"parts": len(expected), "geometry_identical": True,
        "timing_scope": "MCP service transaction API with real disposable workers and persistence; excludes MCP transport, rendering and final checks",
        "individual": {"construction_requests": len(expected), "batch_validations": len(expected),
                       "construction_seconds": baseline_seconds, "validation_seconds": validation_seconds, "repairs": 0},
        "hybrid": {"construction_requests": 1, "batch_validations": 1,
                   "construction_seconds": hybrid_seconds, "validation_seconds": built["validation"]["seconds"], "repairs": 0},
        "request_reduction": 1-1/len(expected), "construction_speedup": baseline_seconds/hybrid_seconds,
        "final_stability": {"individual": baseline_final["stability"], "hybrid": hybrid_final["stability"]},
        "native_graph_edges": len(hybrid_final["graph"]["edges"])}
    write_json(output / "benchmark.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
