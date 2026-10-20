"""Maintainer utility: freeze the curated LDraw/BrickNet subset as package data."""

import json
import lzma
from importlib.metadata import distribution
from pathlib import Path

from lego_mcp.parts import BUILTIN_PARTS
from legoworld.geometry import mesh

ADDITIONS = "3040b 3039 3037 3298 3297 3659 3307 4490 3062b 3941 6141 4032a 3942c 4589 98138 87079 4150 14719 2420 3794b 15573 87580 60479 3032 11477 15068 50950 54200".split()

data = distribution("bricknet").locate_file("bricknet/_data/v1")
labels = json.loads(lzma.decompress((data / "labels.json.xz").read_bytes()))
names = json.loads((data / "part_names.json").read_text(encoding="utf-8"))
aliases = {r["src"]: r for r in json.loads(lzma.decompress((data / "part_aliases.json.xz").read_bytes()))["rows"]}
base = [pid for pid, p in BUILTIN_PARTS.items()
        if p.name.startswith(("Brick ", "Plate ", "Tile ", "Baseplate ")) and pid != "3857"]
records = {}
for pid in base + ADDITIONS:
    triangles, _ = mesh(pid + ".dat")
    low, high = triangles.min((0, 1)), triangles.max((0, 1))
    canonical = pid if pid in names else aliases[pid]["dst"]
    wrapper = aliases[pid]["final_matrix_3x4"] if canonical != pid else [0,0,0,1,0,0,0,1,0,0,0,1]
    label = labels[canonical + ".dat"]
    import numpy as np
    def transform(point):
        return (np.array(wrapper[3:]).reshape(3,3) @ point + wrapper[:3]).tolist()
    # Upright system connections only; side studs/axles/clips are not advertised.
    studs = [row[:3] for rows in label.get("stud", {}).values() for row in rows
             if all(abs(v) < .01 for v in row[3:5])]
    holes = label.get("hole", {})
    receivers = [row[:3] for row in holes.get("hole", [])
                 if all(abs(v) < .01 for v in row[3:5])]
    if not receivers:
        receivers = [row[:3] for row in holes.get("tube", [])
                     if all(abs(v) < .01 for v in row[3:5])]
    studs = [transform(p) for p in studs]
    receivers = [transform(p) for p in receivers]
    bottom = max((row[1] for row in receivers), default=float(high[1]))
    # Standard parts with a single bottom mating plane. Their upright body top
    # is y=0; studs extend to y=-4 and are excluded from the body height.
    origin = [round(float((low[0]+high[0])/2), 3), float(bottom), round(float((low[2]+high[2])/2), 3)]
    top = min((row[1] for row in studs), default=float(low[1]))
    size = [round(float(high[0]-low[0])/20)*20, round(float(high[2]-low[2])/20)*20, float(bottom-top)]
    if pid in base:
        # Retain the v1 placement grid for its common rectangular parts.
        p = BUILTIN_PARTS[pid]
        origin, size = [0, p.height, 0], [p.width, p.depth, p.height]
    name = names[canonical]
    records[pid] = {"name": name.capitalize(), "category": name.split()[0],
                    "origin": origin, "size": size, "bbox": [low.tolist(), high.tolist()],
                    "studs": studs, "receivers": receivers, "added_in_v2": pid in ADDITIONS,
                    "collider": canonical, "collider_transform": wrapper}
target = Path(__file__).resolve().parents[1] / "src/legoworld/catalog.json"
entries = ["  " + json.dumps(pid) + ": {\n" + ",\n".join(
    "    " + json.dumps(key) + ": " + json.dumps(value) for key, value in record.items())
    + "\n  }" for pid, record in records.items()]
target.write_text("{\n" + ",\n".join(entries) + "\n}\n", encoding="utf-8")
print(f"Wrote {len(records)} parts, {len(ADDITIONS)} additions: {target}")
