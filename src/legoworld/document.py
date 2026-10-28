"""Stable occurrence paths and copy-on-write editing of a JSON assembly DAG."""

from copy import deepcopy

from legoworld.backend import b, pack, pose, pose_data, uid


def empty(name="model"):
    return pack(b.Assembly(name))


def entries(doc):
    out = {"root": {"id": "root", "assembly": True, "definition": doc["root"],
                    "pose": pose_data(b.ID), "world_pose": pose_data(b.ID), "color": 16,
                    "name": doc["name"], "parent": None}}

    def visit(key, prefix, parent_pose, inherited, ancestors):
        if key in ancestors:
            raise ValueError("Cyclic component definitions")
        record = doc["definitions"][key]
        for child in record["children"]:
            node_id = prefix + "/" + child["id"]
            world = parent_pose @ pose(child["pose"])
            color = inherited if child["color"] in (None, 16) else child["color"]
            out[node_id] = {"id": node_id, "assembly": child["assembly"],
                "definition": child["what"] if child["assembly"] else None,
                "part_id": None if child["assembly"] else child["what"],
                "name": doc["definitions"][child["what"]]["name"] if child["assembly"] else child["what"],
                "pose": child["pose"], "world_pose": pose_data(world), "color": color,
                "parent": prefix}
            if child["assembly"]:
                visit(child["what"], node_id, world, color, ancestors | {key})
    visit(doc["root"], "root", b.ID, 16, set())
    return out


def owner(doc, node_id, writable=False):
    """Return a component definition, cloning each ancestor along this instance path."""
    if node_id != "root" and not node_id.startswith("root/"):
        raise KeyError(f"Unknown node {node_id!r}")
    key = doc["root"]
    for segment in node_id.split("/")[1:]:
        child = next(c for c in doc["definitions"][key]["children"] if c["id"] == segment)
        if not child["assembly"]:
            raise ValueError("Expected a component")
        key = child["what"]
        if writable:
            new_key = uid()
            doc["definitions"][new_key] = deepcopy(doc["definitions"][key])
            child["what"] = new_key
            key = new_key
    return doc["definitions"][key]


def child_record(doc, node_id, writable=False):
    parent, segment = node_id.rsplit("/", 1)
    record = owner(doc, parent, writable)
    return next(c for c in record["children"] if c["id"] == segment)


def prune(doc):
    keep = set()
    def visit(key):
        if key in keep:
            return
        keep.add(key)
        for c in doc["definitions"][key]["children"]:
            if c["assembly"]:
                visit(c["what"])
    visit(doc["root"])
    doc["definitions"] = {k: v for k, v in doc["definitions"].items() if k in keep}


def subtree_ids(doc, target):
    return {i for i in entries(doc) if i == target or i.startswith(target + "/")}


def flat_records(doc, model=None):
    """Same order/poses/colors as BrickAgent.parts, with stable document IDs."""
    from legoworld.backend import unpack
    model = unpack(doc) if model is None else model
    ids = [i for i, item in entries(doc).items() if not item["assembly"]]
    return [{"id": node_id, "stem": p.stem, "color": p.color, "pos": list(p.pos),
             "rot": list(p.rot), "path": list(p.path)} for node_id, p in zip(ids, b.parts(model), strict=True)]
