"""Temporary binary snapshots for a separate browser WebGPU device."""

import json
import numpy as np
from ._native import NotebookFigure


class NotebookData:
    def __init__(self, width, height, pool_bytes, retain):
        self.model = NotebookFigure(width, height, pool_bytes)
        self.columns = {}
        self.composites = {}
        self.retain = retain
        self.sealed = False

    def __getattr__(self, key):
        return getattr(self.model, key)

    def _label_column(self, id, field):
        if field is not None:
            record = self.composites.get(id)
            if record is None: return None
            id = record[1].get(field)
        entry = self.columns.get(id)
        if entry is None: return None
        dtype, data = entry
        return np.frombuffer(data, dtype=np.dtype(dtype).newbyteorder('<'))

    def apply_settings(self, value):
        if self.columns:
            from ._native import format_value_labels_json
            value = format_value_labels_json(value, self._label_column, self.model.settings_json())
        return self.model.apply_settings(value)

    def upload_column(self, id, array):
        if self.sealed:
            raise RuntimeError(
                "Notebook columns are sealed after display; create a new Figure to change source data"
            )
        self.model.upload_column(id, array)
        # Independent snapshot: later user mutations must not alter transferred data.
        little = np.asarray(array, dtype=array.dtype.newbyteorder("<"))
        self.columns[id] = (str(array.dtype), little.tobytes(order="C"))

    def upload_composite(self, kind, id, fields):
        if self.sealed:
            raise RuntimeError("Notebook data is sealed after display")
        if kind not in ("record", "ragged", "triangles"):
            raise ValueError("unknown composite kind")
        entries = {}
        for key, array in fields.items():
            a = np.ascontiguousarray(array)
            token = id + "::" + key
            self.columns[token] = (
                str(a.dtype),
                a.astype(a.dtype.newbyteorder("<"), copy=False).tobytes(),
            )
            entries[key] = token
        flat = np.concatenate([np.asarray(a, dtype=float) for a in fields.values()])
        finite = flat[np.isfinite(flat)]
        lo, hi = (
            (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
        )
        self.model.register_composite_metadata(
            id, len(next(iter(fields.values()))), lo, hi
        )
        self.composites[id] = (kind, entries)

    def cache_series_extents(self, spec_json):
        # Only bounded extent metadata survives transfer release, never sample arrays.
        spec = json.loads(spec_json)
        style = next(iter(spec["render_type"].values()))
        if style.get("matrix", {}).get("grid_layout") == "Hexagonal":

            def grid_array(name):
                dtype, data = self.columns[name]
                return np.frombuffer(data, dtype=np.dtype(dtype).newbyteorder("<"))

            x, y = grid_array(spec["x_column"]), grid_array(spec["y_column"])
            dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
            bounds = [
                (float(x.min()) - abs(dx) * 2 / 3, float(x.max()) + abs(dx) * 2 / 3),
                (
                    float(y.min()) - abs(dy) * 0.5 + min(dy, 0) * 0.5,
                    float(y.max()) + abs(dy) * 0.5 + max(dy, 0) * 0.5,
                ),
            ]
            self.model.cache_fit_extent(
                spec["series_id"],
                *[(a, b, a if a > 0 else (b if b > 0 else None)) for a, b in bounds],
            )
        if (
            "Vector" in spec["render_type"]
            and "Data" in style["style"]["scale"]
            and "Points" in style["components"]
        ):

            def vector_array(name):
                dtype, data = self.columns[name]
                return np.frombuffer(
                    data, dtype=np.dtype(dtype).newbyteorder("<")
                ).astype(np.float64)

            x, y = vector_array(spec["x_column"]), vector_array(spec["y_column"])
            u, v = (
                vector_array(style["components"]["Points"][key]) for key in ("u", "v")
            )
            factor = style["style"]["scale"]["Data"]["factor"]
            pivot = style["style"].get("pivot", "Tail")
            start, end = {"Tail": (0, 1), "Middle": (-0.5, 0.5), "Tip": (-1, 0)}[pivot]
            valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(u) & np.isfinite(v)
            extents = []
            for origin, component in ((x, u), (y, v)):
                values = np.concatenate(
                    (
                        (origin + start * factor * component)[valid],
                        (origin + end * factor * component)[valid],
                    )
                )
                values = values[np.isfinite(values)]
                if not values.size:
                    raise ValueError("vector has no finite geometry")
                positive = values[values > 0]
                extents.append(
                    (
                        float(values.min()),
                        float(values.max()),
                        float(positive.min()) if positive.size else None,
                    )
                )
            self.model.cache_fit_extent(spec["series_id"], *extents)
        if "err_x" in style or "err_y" in style:

            def array(name):
                dtype, data = self.columns[name]
                return np.frombuffer(
                    data, dtype=np.dtype(dtype).newbyteorder("<")
                ).astype(np.float64)

            x, y = array(spec["x_column"]), array(spec["y_column"])
            valid = np.isfinite(x) & np.isfinite(y)
            extents = []
            for axis, values in [("x", x), ("y", y)]:
                ref = style.get("err_" + axis)
                if ref is None:
                    values = values[valid]
                else:
                    if "Symmetric" in ref:
                        lo = hi = array(ref["Symmetric"]["column"])
                    else:
                        lo, hi = (
                            array(ref["Asymmetric"][k]) for k in ("lower", "upper")
                        )
                    values = np.concatenate(
                        (values[valid], (values - lo)[valid], (values + hi)[valid])
                    )
                values = values[np.isfinite(values)]
                if not values.size:
                    raise ValueError("errorbar has no finite paired samples")
                positive = values[values > 0]
                extents.append(
                    (
                        float(values.min()),
                        float(values.max()),
                        float(positive.min()) if positive.size else None,
                    )
                )
            self.model.cache_fit_extent(spec["series_id"], *extents)

    def add_series_fitted(self, spec_json, config=None, bounds=None):
        self.cache_series_extents(spec_json)
        return self.model.add_series_fitted(spec_json, config, bounds)

    def add_series_batch(self, spec_json, config_json):
        specs = json.loads(spec_json)
        config = json.loads(config_json)

        def array(name):
            dtype, data = self.columns[name]
            return np.frombuffer(data, dtype=np.dtype(dtype).newbyteorder("<"))

        def extent(values):
            values = np.asarray(values)
            finite = values[np.isfinite(values)]
            if not finite.size:
                return (0.0, 0.0, None)
            positive = finite[finite > 0]
            return (
                float(finite.min()),
                float(finite.max()),
                float(positive.min()) if positive.size else None,
            )

        all_specs = json.loads(self.model.settings_json())["series"] + specs
        for spec in specs:
            self.cache_series_extents(json.dumps(spec))
            kind, style = next(iter(spec["render_type"].items()))
            local = next(
                (
                    p["config"]
                    for p in config.get("subplots", [])
                    if spec["series_id"] in p.get("series", [])
                ),
                config,
            )
            direction = local.get("bar_groups", {}).get("direction", "Vertical")
            if kind == "CategoryBars":
                group = [
                    array(s["y_column"] if direction == "Vertical" else s["x_column"])
                    for s in all_specs
                    if "CategoryBars" in s["render_type"]
                    and local
                    is next(
                        (
                            p["config"]
                            for p in config.get("subplots", [])
                            if s["series_id"] in p.get("series", [])
                        ),
                        config,
                    )
                ]
                mode = local.get("bar_groups", {}).get("mode", "Grouped")
                if mode == "PercentStacked":
                    data = np.array(
                        [-100.0 if any(np.any(v < 0) for v in group) else 0.0, 100.0]
                    )
                elif mode == "Stacked":
                    matrix = np.asarray(group)
                    data = np.r_[
                        np.nansum(np.maximum(matrix, 0), axis=0),
                        np.nansum(np.minimum(matrix, 0), axis=0),
                        0.0,
                    ]
                else:
                    data = np.r_[np.concatenate(group), 0.0]
                position = (
                    0.0,
                    0.0,
                    None,
                )  # The categorical position axis keeps its configured window.
                pair = (
                    [position, extent(data)]
                    if direction == "Vertical"
                    else [extent(data), position]
                )
            elif kind == "BoxPlot":
                vals = []
                record = self.composites.get(spec["y_column"])
                if record:
                    vals.extend(
                        array(token)
                        for name, token in record[1].items()
                        if name != "sample_count"
                    )

                def curves(value):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            if key == "curve":
                                yield item
                            else:
                                yield from curves(item)

                for ref in [style.get("outliers"), *curves(style.get("violin"))]:
                    if ref in self.composites:
                        vals.append(array(self.composites[ref][1]["values"]))
                if not vals:
                    continue
                position = (0.0, 0.0, None)
                pair = (
                    [position, extent(np.concatenate(vals))]
                    if direction == "Vertical"
                    else [extent(np.concatenate(vals)), position]
                )
            elif kind == "RangeBars":
                values = [array(spec["y_column"]), array(style["start"])]
                if style.get("whiskers"):
                    values.extend(
                        array(style["whiskers"][key]) for key in ("low", "high")
                    )
                positions = array(spec["x_column"])
                width = style.get("slot_width") or 0.0
                pos = extent(np.r_[positions - width / 2, positions + width / 2])
                pair = (
                    [pos, extent(np.concatenate(values))]
                    if direction == "Vertical"
                    else [extent(np.concatenate(values)), pos]
                )
            else:
                continue
            self.model.cache_fit_extent(spec["series_id"], *pair)
        from ._native import format_value_labels_json
        previous = self.model.settings_json()
        candidate = json.loads(previous)
        candidate.update(config=config, series=all_specs)
        formatted = json.loads(format_value_labels_json(json.dumps(candidate, allow_nan=False), self._label_column, previous))
        return self.model.add_series_batch(spec_json, config_json, json.dumps(formatted['series'], allow_nan=False))

    def remove_column(self, id):
        self.model.remove_column(id)
        self.columns.pop(id, None)
        if id in self.composites:
            for token in self.composites.pop(id)[1].values():
                self.columns.pop(token, None)

    def payload(self):
        if (
            self.sealed
            and not self.columns
            and not any(
                json.loads(self.model.settings_json()).get(k)
                for k in ("radial", "categorical", "boxplot", "radar")
            )
        ):
            raise RuntimeError(
                "Notebook transfer snapshots were released; create a new Figure, or set retain_notebook_data=True before upload"
            )
        self.sealed = True
        manifest, buffers = [], []
        fields = {
            token: dict(resource=id, kind=kind, field=key)
            for id, (kind, entries) in self.composites.items()
            for key, token in entries.items()
        }
        for id, (dtype, data) in self.columns.items():
            manifest.append(
                dict(id=id, dtype=dtype, bytes=len(data), **fields.get(id, {}))
            )
            buffers.append(data)
        return manifest, buffers

    def acknowledged(self):
        if not self.retain:
            self.columns.clear()
