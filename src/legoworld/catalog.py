"""Curated upright parts with explicit origins and measured stud layouts."""

import json
from importlib.resources import files

from lego_mcp.parts import Part
from lego_mcp import connectors

RECORDS = json.loads((files("legoworld") / "catalog.json").read_text(encoding="utf-8"))


def bottom_origin(part_id: str) -> tuple[float, float, float]:
    """Point in standard LDraw coordinates used as the engine origin."""
    return tuple(RECORDS[part_id]["origin"])


def install() -> dict[str, Part]:
    catalog = {}
    connectors.invalidate_definitions()
    for pid, record in RECORDS.items():
        origin = record["origin"]
        studs = tuple(tuple(p[i]-origin[i] for i in range(3)) for p in record["studs"])
        receivers = tuple(tuple(p[i]-origin[i] for i in range(3)) for p in record["receivers"])
        catalog[pid] = Part(pid, record["name"], *record["size"], studs, receivers,
                            tuple(tuple(p[i]-origin[i] for i in range(3)) for p in record["bbox"]))
        # Override the upstream's synthesized full-footprint studs/receivers.
        points = tuple(connectors.Connector(connectors.ConnectorType.STUD_TOP, *p) for p in studs)
        points += tuple(connectors.Connector(connectors.ConnectorType.STUD_RECEIVER_BOTTOM, *p) for p in receivers)
        connectors.SUPPORTED_DEFINITIONS[pid] = connectors.PartDefinition(
            pid, record["name"], round(record["size"][0]/20), round(record["size"][1]/20),
            max(1, round(record["size"][2]/8)), points)
    return catalog
