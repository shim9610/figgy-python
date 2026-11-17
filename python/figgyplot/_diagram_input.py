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


def records(value, name, rich):
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
        row = plain(row)
        if not isinstance(row, dict):
            raise TypeError(f"{name}[{index}] must be a record mapping")
        if isinstance(row.get("label"), str):
            from .figure import _segments

            label = copy.deepcopy(rich)
            label["segments"] = _segments(row["label"])
            row["label"] = label
        if isinstance(row.get("momentum"), dict) and isinstance(
            row["momentum"].get("label"), str
        ):
            from .figure import _segments

            label = copy.deepcopy(rich)
            label["segments"] = _segments(row["momentum"]["label"])
            row["momentum"]["label"] = label
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
