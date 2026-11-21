"""Protect destination scientific data when replaying exported appearance."""

import copy
from collections import deque


def _bindings(spec):
    result = {key: spec.get(key) for key in ("x_column", "y_column", "z_column")}

    def visit(value, path=()):
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key == "column"
                    or key == "columns"
                    or key.endswith("_column")
                    or key in ("triangles", "densities", "raw")
                ):
                    result[path + (key,)] = item
                else:
                    visit(item, path + (key,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, path + (index,))

    visit(spec["render_type"])
    return result


def _records(source, destination, *, visual, topology=()):
    by_id = {row["id"]: row for row in destination}
    if {row["id"] for row in source} != set(by_id):
        raise ValueError("appearance replay requires matching diagram record IDs")
    result = []
    for row in source:
        current = by_id[row["id"]]
        if any(row.get(key) != current.get(key) for key in topology):
            raise ValueError("appearance replay requires matching diagram topology")
        kept = copy.deepcopy(current)
        for key in visual:
            if key in row:
                kept[key] = copy.deepcopy(row[key])
            else:
                kept.pop(key, None)
        result.append(kept)
    return result


def preserve_data(source, destination):
    """Modify a detached source document only after validating its data layout."""
    source_panels = source.get("identity", {}).get("panels")
    dest_panels = destination.get("identity", {}).get("panels")
    if source_panels != dest_panels:
        raise ValueError("appearance replay requires matching panel and overlay IDs")
    source_configs = [source["config"]] + [
        p["config"] for p in source["config"].get("subplots", [])
    ]
    dest_configs = [destination["config"]] + [
        p["config"] for p in destination["config"].get("subplots", [])
    ]
    if len(source_configs) != len(dest_configs):
        raise ValueError("appearance replay requires matching panels")
    for expected, current in zip(source_configs, dest_configs):
        for side in ("bottom_x", "top_x", "left_y", "right_y"):
            categories = lambda cfg: [c["id"] for c in cfg[side].get("categories", [])]
            if categories(expected) != categories(current):
                raise ValueError(
                    "appearance replay requires matching category IDs and order"
                )
    old = {spec["series_id"]: spec for spec in destination["series"]}
    if {s["series_id"] for s in source["series"]} != set(old):
        raise ValueError("appearance replay requires matching series IDs")
    for spec in source["series"]:
        current = old[spec["series_id"]]
        kind, body = next(iter(spec["render_type"].items()))
        old_kind, old_body = next(iter(current["render_type"].items()))
        if kind != old_kind:
            raise ValueError("appearance replay requires matching chart kinds")
        if kind == "EnergyLevels":
            for key in ("levels", "limits", "transitions", "bands"):
                body[key] = _records(
                    body.get(key, []),
                    old_body.get(key, []),
                    visual=("label", "label_offset", "x_offset", "color") if key == "transitions"
                    else ("label", "label_offset", "x_offset"),
                    topology=("column", "lower", "upper", "first", "last"),
                )
            if body.get("source") != old_body.get("source"):
                raise ValueError(
                    "appearance replay requires matching energy-level sources"
                )
        elif kind == "Feynman":
            body["vertices"] = _records(
                body.get("vertices", []),
                old_body.get("vertices", []),
                visual=("at", "marker", "label", "label_offset"),
                topology=("role",),
            )
            body["propagators"] = _records(
                body.get("propagators", []),
                old_body.get("propagators", []),
                visual=(
                    "bend",
                    "label",
                    "label_offset",
                    "momentum",
                    "color",
                    "width_px",
                ),
                topology=("from", "to", "particle"),
            )
        elif kind == "RangeLinks":
            # Offsets style matched links. The destination owns its bar binding
            # and endpoints, including links without a counterpart in the source.
            offsets = {}
            if body["bars"] == old_body["bars"]:
                for link in body.get("links", []):
                    offsets.setdefault((link["from"], link["to"]), deque()).append(
                        link.get("exit_offset")
                    )
            body["bars"] = old_body["bars"]
            body["links"] = copy.deepcopy(old_body.get("links", []))
            for link in body["links"]:
                matches = offsets.get((link["from"], link["to"]))
                if matches:
                    offset = matches.popleft()
                    if offset is None:
                        link.pop("exit_offset", None)
                    else:
                        link["exit_offset"] = offset
        elif _bindings(spec) != _bindings(current):
            raise ValueError(
                "appearance replay requires matching source column bindings"
            )
        if "labels" in body and isinstance(body["labels"], dict):
            before, after = old_body.get("labels", {}), body["labels"]
            if "text" in before:
                after["text"] = copy.deepcopy(before["text"])
            else:
                after.pop("text", None)
