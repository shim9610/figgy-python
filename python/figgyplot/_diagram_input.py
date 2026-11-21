"""Normalize scientific records before publishing a diagram transaction."""

import copy
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass

import numpy as np


def plain(value):
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if is_dataclass(value) and not isinstance(value, type):
        return plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def records(value, name, rich, *, dpi=120):
    """Accept row records, structured arrays and DataFrame-like tables."""
    if hasattr(value, "to_dict") and not isinstance(value, Mapping):
        value = value.to_dict("records")
    if isinstance(value, np.ndarray) and value.dtype.names:
        value = [{key: row[key] for key in value.dtype.names} for row in value]
    if isinstance(value, Mapping):
        if "id" in value and isinstance(value["id"], (str, np.str_)):
            value = [value]
        else:
            keys = list(value)
            columns = [value[k] for k in keys]
            try:
                lengths = [len(column) for column in columns]
            except TypeError:
                raise TypeError(
                    f"{name} must contain row records or equal-length columns"
                ) from None
            if len(set(lengths)) > 1:
                raise ValueError(f"{name} columns must have equal lengths")
            value = [dict(zip(keys, row)) for row in zip(*columns)]
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} expects records; use read_nist() for a NIST CSV file")
    output = []
    try:
        iterator = iter(value)
    except TypeError:
        raise TypeError(f"{name} must be a table or iterable of records") from None
    for index, row in enumerate(iterator):
        raw_label = row.get("label") if isinstance(row, Mapping) else None
        raw_momentum = row.get("momentum") if isinstance(row, Mapping) else None
        row = plain(row)
        if not isinstance(row, dict):
            raise TypeError(f"{name}[{index}] must be a record mapping")
        if name == "propagators":
            for alias, canonical in [
                ("from_", "from"),
                ("source", "from"),
                ("target", "to"),
            ]:
                if alias in row:
                    if canonical in row and row[canonical] != row[alias]:
                        raise ValueError(
                            "conflicting propagator " + canonical + " aliases"
                        )
                    row[canonical] = row.pop(alias)
            if "particle" in row:
                row["particle"] = enum_name(row["particle"], PARTICLES)
        if name == "vertices" and "role" in row:
            row["role"] = enum_name(row["role"], ("Incoming", "Outgoing", "Internal"))
        from ._richtext import TextRun

        styled = isinstance(raw_label, TextRun) or (
            isinstance(raw_label, (list, tuple))
            and any(isinstance(v, TextRun) for v in raw_label)
        )
        if isinstance(row.get("label"), str) or styled:
            from .figure import _segments

            label = copy.deepcopy(rich)
            label["segments"] = _segments(
                raw_label if styled else row["label"], dpi=dpi
            )
            row["label"] = label
        if isinstance(row.get("momentum"), dict):
            momentum = row["momentum"]
            raw = (
                raw_momentum.get("label") if isinstance(raw_momentum, Mapping) else None
            )
            styled = isinstance(raw, TextRun) or (
                isinstance(raw, (list, tuple))
                and any(isinstance(v, TextRun) for v in raw)
            )
            if isinstance(momentum.get("label"), str) or styled:
                from .figure import _segments

                label = copy.deepcopy(rich)
                label["segments"] = _segments(
                    raw if styled else momentum["label"], dpi=dpi
                )
                momentum["label"] = label
            if "side" in momentum:
                momentum["side"] = enum_name(momentum["side"], ("Left", "Right"))
        output.append(row)
    return output


def require(records, fields, name):
    seen = set()
    for index, row in enumerate(records):
        missing = set(fields) - row.keys()
        if missing:
            raise ValueError(
                f"{name}[{index}] is missing: {', '.join(sorted(missing))}"
            )
        if not isinstance(row["id"], str) or not row["id"]:
            raise ValueError(f"{name}[{index}].id must be a nonempty string")
        if row["id"] in seen:
            raise ValueError(f"duplicate {name} id: {row['id']}")
        seen.add(row["id"])
    return seen


PARTICLES = (
    "Plain",
    "Fermion",
    "AntiFermion",
    "Photon",
    "ChargedBoson",
    "Gluon",
    "Scalar",
    "ChargedScalar",
    "Ghost",
    "Majorana",
    "Graviton",
    "DoubleLine",
)


def enum_name(value, names):
    if not isinstance(value, str):
        raise TypeError("diagram choice must be a string")
    key = "".join(c for c in value.casefold() if c.isalnum())
    match = next(
        (n for n in names if "".join(c for c in n.casefold() if c.isalnum()) == key),
        None,
    )
    if match is None:
        raise ValueError("expected one of: " + ", ".join(names))
    return match
