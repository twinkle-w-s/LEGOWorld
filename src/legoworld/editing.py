"""Atomic edits on a hierarchy; no in-place mutation of native Occurrences."""

from copy import deepcopy

from legoworld.backend import b, pack, pose, pose_data, uid, native_index, unpack
from legoworld.document import owner, child_record, entries, subtree_ids, prune


def endpoint(doc, selector):
    node = selector["node_id"]
    item = entries(doc)[node]
    if item["assembly"]:
        ref = owner(doc, node)["ports"][selector["port"]]
        return {"path": node.split("/")[1:] + ref["path"], "connector": ref["connector"]}
    return {"path": node.split("/")[1:],
            "connector": native_index(item["part_id"], selector["type"], selector["index"])}


def native_connector(doc, ref):
    model, path = unpack(doc), []
    record = doc["definitions"][doc["root"]]
    for segment in ref["path"]:
        i = next(i for i, c in enumerate(record["children"]) if c["id"] == segment)
        occurrence = model.children[i]
        path.append(occurrence)
        child = record["children"][i]
        if child["assembly"]:
            model, record = occurrence.what, doc["definitions"][child["what"]]
    return b.Connector(tuple(path), ref["connector"])


def set_world_pose(doc, node, world):
    parent = node.rsplit("/", 1)[0]
    parent_pose = pose(entries(doc)[parent]["world_pose"])
    child_record(doc, node, True)["pose"] = pose_data(parent_pose.inv @ world)


def join(doc, a, c):
    common = []
    for x, y in zip(a["path"][:-1], c["path"][:-1]):
        if x != y:
            break
        common.append(x)
    record = owner(doc, "/".join(["root", *common]), True)
    pair = [{"path": ref["path"][len(common):], "connector": ref["connector"]} for ref in (a, c)]
    if pair not in record["joins"] and list(reversed(pair)) not in record["joins"]:
        record["joins"].append(pair)


def detach(doc, a, c):
    found = False
    for node, item in list(entries(doc).items()):
        if not item["assembly"]:
            continue
        prefix = node.split("/")[1:]
        original = owner(doc, node)
        keep = []
        for pair in original["joins"]:
            absolute = [{"path": prefix + r["path"], "connector": r["connector"]} for r in pair]
            if absolute == [a, c] or absolute == [c, a]:
                found = True
            else:
                keep.append(pair)
        if len(keep) != len(original["joins"]):
            owner(doc, node, True)["joins"] = keep
    if not found:
        raise ValueError("No authored join matches; inferred graph edges cannot be detached")


def attach(doc, source, source_selector, target_selector, options):
    a, c = endpoint(doc, target_selector), endpoint(doc, source_selector)
    source_path = source.split("/")[1:]
    if c["path"][:len(source_path)] != source_path:
        raise ValueError("by must be a connector inside the moving instance")
    if a["path"][:len(source_path)] == source_path:
        raise ValueError("Cannot attach an instance to itself or its descendants")
    target, moving = native_connector(doc, a), native_connector(doc, c)
    world = pose(entries(doc)[source]["world_pose"])
    # placement() maps the source connector's enclosing frame to the target frame.
    # Present a source-local connector, rather than treating its world frame as local.
    from legoworld.backend import relative_connector
    moving = relative_connector(moving, world.inv)
    opts = {k: options[k] for k in ("yaw", "flip", "slide", "seat", "align") if k in options}
    if options.get("orient") is not None:
        opts["orient"] = pose(options["orient"])
    set_world_pose(doc, source, b.placement(target, moving, **opts))
    join(doc, a, c)


def remap_part_references(doc, node, connector_map, new_stem):
    for owner_id, item in list(entries(doc).items()):
        if not item["assembly"]:
            continue
        prefix = owner_id.split("/")[1:]
        original = owner(doc, owner_id)
        refs = [r for pair in original["joins"] for r in pair] + list(original["ports"].values())
        if not any("/".join(["root", *prefix, *r["path"]]) == node for r in refs):
            continue
        record = owner(doc, owner_id, True)
        for ref in [r for pair in record["joins"] for r in pair] + list(record["ports"].values()):
            if "/".join(["root", *prefix, *ref["path"]]) == node:
                mapped = connector_map.get(str(ref["connector"]))
                if mapped is None:
                    raise ValueError("Replacement needs connector_map for every referenced native connector")
                ref["connector"] = native_index(new_stem, mapped["type"], mapped["index"])


def apply_operations(doc, operations):
    result, aliases = deepcopy(doc), {}
    made, affected = [], []
    for index, raw in enumerate(operations):
        def expand(value):
            if isinstance(value, str) and value.startswith("$"):
                head, sep, tail = value[1:].partition("/")
                return aliases[head] + (sep + tail if sep else "")
            if isinstance(value, dict):
                return {k: expand(v) for k, v in value.items()}
            if isinstance(value, list):
                return [expand(v) for v in value]
            return value
        try:
            op = expand(deepcopy(raw))
            kind, node = op["op"], op.get("node_id")
            if kind in ("add", "instance"):
                parent = op.get("parent_id", "root")
                if kind == "add":
                    what, assembly = b.resolve(op["part_id"]), False
                else:
                    source = entries(result)[op["source_id"]]
                    if not source["assembly"]:
                        raise ValueError("instance source must be a component")
                    what, assembly = source["definition"], True
                record = {"id": uid(), "assembly": assembly, "what": what,
                          "pose": pose_data(pose(op.get("pose"))),
                          "color": b.color(op["color"]) if op.get("color") is not None else None}
                owner(result, parent, True)["children"].append(record)
                node = parent + "/" + record["id"]
                made.append(node)
                if raw.get("as"):
                    if raw["as"] in aliases:
                        raise ValueError("Repeated operation alias")
                    aliases[raw["as"]] = node
            elif kind == "recolor":
                child_record(result, node, True)["color"] = b.color(op["color"])
            elif kind == "transform":
                selected = op.get("node_ids", [node])
                if not selected or any(n == "root" for n in selected):
                    raise ValueError("Select at least one non-root instance")
                if any(a != c and c.startswith(a + "/") for a in selected for c in selected):
                    raise ValueError("Do not select both a component and its descendant")
                delta, before = pose(op.get("pose")), entries(result)
                for n in dict.fromkeys(selected):
                    set_world_pose(result, n, delta @ pose(before[n]["world_pose"]))
            elif kind == "replace":
                record = child_record(result, node)
                if record["assembly"]:
                    raise ValueError("Use replace_component for assemblies")
                new = b.resolve(op["part_id"])
                if record["what"] != new:
                    remap_part_references(result, node, op.get("connector_map", {}), new)
                    child_record(result, node, True)["what"] = new
            elif kind == "remove":
                child_record(result, node)  # Do not silently accept stale IDs.
                parent, local = node.rsplit("/", 1)
                record = owner(result, parent, True)
                record["children"] = [c for c in record["children"] if c["id"] != local]
            elif kind in ("connect", "detach"):
                a, c = endpoint(result, op["a"]), endpoint(result, op["b"])
                (join if kind == "connect" else detach)(result, a, c)
            elif kind == "attach":
                attach(result, node, op["by"], op["to"], op)
            elif kind == "drop_port":
                del owner(result, node, True)["ports"][op["name"]]
            else:
                raise ValueError(f"Unknown operation {kind!r}")
            if node:
                affected.append(node)
        except (KeyError, ValueError, IndexError, StopIteration, TypeError) as error:
            raise ValueError(f"Operation {index} ({raw.get('op')}): {error}") from error
    prune(result)
    return result, {"created_ids": made, "affected_ids": affected, "aliases": aliases}


def integrate(doc, component, mode, target_id="root", placement=None, mount=None):
    if mode == "replace_model" and target_id != "root":
        raise ValueError("replace_model requires target_id=root")
    result, incoming = deepcopy(doc), pack(component)
    old_ids = subtree_ids(doc, target_id) if mode in ("replace_component", "replace_model") else set()
    if mode == "replace_model":
        incoming.update({"model_id": doc["model_id"], "revision": doc["revision"], "recipes": doc.get("recipes", [])})
        return incoming, {"target_id": "root", "invalidated_ids": sorted(old_ids - {"root"})}
    if mode not in ("add_component", "replace_component"):
        raise ValueError("mode must be replace_model, add_component or replace_component")
    result["definitions"].update(incoming["definitions"])
    if mode == "add_component":
        parent = target_id
        record = {"id": uid(), "assembly": True, "what": incoming["root"],
                  "pose": pose_data(pose(placement)), "color": None}
        owner(result, parent, True)["children"].append(record)
        target_id = parent + "/" + record["id"]
    else:
        if target_id == "root" or not entries(doc)[target_id]["assembly"]:
            raise ValueError("replace_component requires a non-root component instance")
        old_ports, new_ports = owner(doc, target_id)["ports"], incoming["definitions"][incoming["root"]]["ports"]
        prefix = target_id.split("/")[1:]
        for owning_id, item in list(entries(result).items()):
            if not item["assembly"] or owning_id == target_id or owning_id.startswith(target_id + "/"):
                continue
            own_prefix = owning_id.split("/")[1:]
            original = owner(result, owning_id)
            refs = [r for pair in original["joins"] for r in pair] + list(original["ports"].values())
            if not any((own_prefix + r["path"])[:len(prefix)] == prefix for r in refs):
                continue
            record = owner(result, owning_id, True)
            for ref in [r for pair in record["joins"] for r in pair] + list(record["ports"].values()):
                absolute = own_prefix + ref["path"]
                if absolute[:len(prefix)] != prefix:
                    continue
                local = {"path": absolute[len(prefix):], "connector": ref["connector"]}
                names = [n for n, p in old_ports.items() if p == local]
                if len(names) != 1 or names[0] not in new_ports:
                    raise ValueError("External connection has no unique matching named port on replacement")
                replacement = new_ports[names[0]]
                ref.update({"path": prefix[len(own_prefix):] + replacement["path"], "connector": replacement["connector"]})
        record = child_record(result, target_id, True)
        record["what"] = incoming["root"]
        if placement is not None:
            record["pose"] = pose_data(pose(placement))
    if mount:
        attach(result, target_id, {"node_id": target_id, "port": mount["by"]}, mount["to"], mount)
    prune(result)
    return result, {"target_id": target_id, "invalidated_ids": sorted(old_ids - {target_id}),
                    "replacement_discards_local_edits": mode == "replace_component"}
