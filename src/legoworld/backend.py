"""Pinned BrickAgent bridge. All accesses to upstream private members live here."""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import json
import re
from functools import lru_cache
from importlib.metadata import distribution
from importlib.resources import files
from uuid import uuid4

from bricknet import data


@lru_cache(maxsize=1)
def _utf8_names():
    path = distribution("bricknet").locate_file("bricknet/_data/v1/part_names.json")
    return json.loads(path.read_text(encoding="utf-8"))


# BrickNet 0.1.1 otherwise uses the Windows locale for its UTF-8 name table.
data._part_names = _utf8_names
import brickagent as b


def uid():
    return uuid4().hex


def tables(name):
    return b.catalog._load(name)


@lru_cache(maxsize=1)
def palette():
    rows = json.loads((files("brickagent") / "_data/v1/colors.json").read_text(encoding="utf-8"))["colors"]
    return {r["code"]: tuple(bytes.fromhex(r["hex"].lstrip("#"))) for r in rows}


def color_rgb(code):
    return ((code >> 16) & 255, (code >> 8) & 255, code & 255) if code >= 0x2000000 else palette().get(code, (160, 160, 160))


def pose(value=None):
    if value is None:
        return b.ID
    if isinstance(value, b.Pose):
        return value
    return b.Pose(tuple(value.get("rot", b.ID.rot)), tuple(value.get("t", (0, 0, 0))))


def pose_data(value):
    return {"rot": list(value.rot), "t": list(value.t)}


def pack(root):
    """Serialize definitions once, retaining sharing, connector paths and authored joins."""
    if not isinstance(root, b.Assembly):
        raise TypeError("build() must return brickagent.Assembly")
    definitions, keys = {}, {}

    def visit(model):
        if model in keys:
            return keys[model]
        key = keys[model] = uid()
        record = definitions[key] = {"name": model.name, "children": [], "joins": [], "ports": {}}
        for child in model.children:
            record["children"].append({"id": uid(), "assembly": isinstance(child.what, b.Assembly),
                "what": visit(child.what) if isinstance(child.what, b.Assembly) else child.what,
                "pose": pose_data(child.pose), "color": child.color})

        def reference(connector):
            owner, path = model, []
            for occurrence in connector.path:
                path.append(definitions[keys[owner]]["children"][occurrence.index]["id"])
                owner = occurrence.what
            return {"path": path, "connector": connector.native_index}

        record["joins"] = [[reference(c) for c in pair] for pair in model._attachments]
        record["ports"] = {name: reference(c) for name, c in getattr(model, "_legoworld_ports", {}).items()}
        return key

    key = visit(root)
    return {"schema_version": 3, "model_id": uid(), "revision": 0, "name": root.name,
            "root": key, "definitions": definitions, "recipes": []}


def unpack(document):
    if type(document.get("schema_version")) is not int or document["schema_version"] != 3:
        raise ValueError("Expected a V3 project document")
    if not isinstance(document.get("model_id"), str) or not re.fullmatch(r"[0-9a-f]{32}", document["model_id"]):
        raise ValueError("Invalid project ID")
    if not isinstance(document.get("name"), str) or type(document.get("revision")) is not int or document["revision"] < 0:
        raise ValueError("Invalid project name or revision")
    definitions, memo, pending = document["definitions"], {}, set()

    def build(key):
        if key in pending:
            raise ValueError("Cyclic component definitions")
        if key in memo:
            return memo[key]
        pending.add(key)
        record = definitions[key]
        model = b.Assembly(record["name"])
        ids = [c["id"] for c in record["children"]]
        if len(set(ids)) != len(ids) or any(not i or "/" in i for i in ids):
            raise ValueError("Invalid or repeated child ID")
        for child in record["children"]:
            model.add(build(child["what"]) if child["assembly"] else child["what"],
                      pose=pose(child["pose"]), color=child["color"])

        def reference(ref):
            owner, native, path = record, model, []
            for child_id in ref["path"]:
                index = next(i for i, c in enumerate(owner["children"]) if c["id"] == child_id)
                occurrence = native.children[index]
                path.append(occurrence)
                child = owner["children"][index]
                if child["assembly"]:
                    owner, native = definitions[child["what"]], occurrence.what
            if not path or isinstance(path[-1].what, b.Assembly):
                raise ValueError("A connector must address a leaf part")
            connector = b.Connector(tuple(path), ref["connector"])
            if not 0 <= connector.native_index < len(b.connectors(connector.stem)):
                raise ValueError("Connector index outside the part's connector table")
            return connector

        model._attachments = [tuple(reference(c) for c in pair) for pair in record["joins"]]
        model._legoworld_ports = {name: reference(ref) for name, ref in record["ports"].items()}
        pending.remove(key)
        memo[key] = model
        return model

    return build(document["root"])


def native_index(stem, kind, index):
    return b.connectors(stem, kind)[index].native_index


def relative_connector(connector, transform):
    """Reframe an occurrence path by prepending a detached carrier assembly."""
    carrier = b.Assembly("source_frame")
    # placement uses connector.pose/type/stem only; the detached carrier is never serialized.
    occurrence = b.Occurrence(None, carrier, transform)
    return b.Connector((occurrence, *connector.path), connector.native_index)


def add_required_contact(component, a, c):
    component._attachments.append((a, c))


def authored_contact_errors(model, graph):
    from brickagent.check import _bricknet_parts, _contact_errors
    flat = b.parts(model)
    _, matrices = _bricknet_parts(flat)
    return list(_contact_errors(model, flat, graph, matrices, b.attachments(model)))
