"""Column-backed chart constructors using the renderer's public model defaults."""

import copy
from contextlib import contextmanager
import json
import math
import numpy as np
from . import _document, _style_runtime
from ._native import series_template_json, coordinate_defaults_json


def template(kind):
    return json.loads(series_template_json(kind))


def _style_update(target, properties):
    unknown = set(properties) - set(target)
    if unknown:
        raise TypeError("unknown style options: " + ", ".join(sorted(unknown)))
    target.update(properties)


def _diagram_style_update(target, properties):
    from .figure import _merge

    unknown = properties.keys() - target.keys()
    if unknown:
        raise TypeError("unknown diagram style options: " + ", ".join(sorted(unknown)))
    _merge(target, properties)


def _rows(data):
    try:
        a = np.asarray(data)
    except ValueError:
        return [np.asarray(row) for row in data]
    if a.ndim == 1 and a.dtype != object:
        return [a]
    return [np.asarray(row) for row in data]


def _range_link_rows(links, dpi):
    from ._validation import number

    rows = []
    for link in links:
        if hasattr(link, "keys"):
            row = dict(link)
        else:
            predecessor, successor = link
            row = {"from": predecessor, "to": successor}
        if not {"from", "to"} <= row.keys() or row.keys() - {"from", "to", "exit_fraction", "exit_offset"}:
            raise ValueError("links require from and to row indices")
        for key in ("from", "to"):
            value = row[key]
            if (
                isinstance(value, (bool, np.bool_))
                or not isinstance(value, (int, np.integer))
                or not 0 <= value < 2**32
            ):
                raise ValueError("link row indices must be unsigned 32-bit integers")
            row[key] = int(value)
        if "exit_offset" in row and "exit_fraction" in row:
            raise ValueError("specify exit_fraction or exit_offset, not both")
        if row.get("exit_fraction") is not None:
            fraction = number(row["exit_fraction"], "exit_fraction")
            if not 0 <= fraction <= 1:
                raise ValueError("exit_fraction must be between 0 and 1")
            row["exit_fraction"] = fraction
        if row.get("exit_offset") is not None:
            row["exit_offset"] = number(row["exit_offset"], "exit_offset") * dpi / 72
        rows.append(row)
    return rows


def _progress_values(values, rows):
    from .figure import _array

    values = _array(values)
    if values.size != rows or not np.all(np.isnan(values) | ((0 <= values) & (values <= 1))):
        raise ValueError("progress requires one fraction in [0, 1] or NaN per bar")
    return values


def _range_progress(column, remaining_opacity):
    from ._validation import number

    opacity = number(remaining_opacity, "remaining opacity")
    if not 0 <= opacity <= 1:
        raise ValueError("remaining opacity must be in [0, 1]")
    return dict(column=column, remaining_opacity=opacity)


@contextmanager
def _edit_range_progress(artist, values, opacity):
    from ._artist_appearance import ColumnReference, _column

    fig = artist.figure
    with fig._lock:
        spec = artist._spec(fig.get_settings())
        body = spec["render_type"].get("RangeBars")
        if body is None:
            raise AttributeError("progress requires range bars")
        current = body.get("progress")
        if values is None:
            yield None
            return
        if values is ...:
            if current is None:
                raise ValueError("set progress before changing its opacity")
            values = current["column"]
        if opacity is None:
            opacity = current["remaining_opacity"] if current is not None else 0.4
        native = fig._native
        rows = native.column_row_count(spec["x_column"])
        if isinstance(values, (str, ColumnReference)):
            name = _column(values, fig)
            if native.column_row_count(name) != rows:
                raise ValueError("progress column must have one value per bar")
            extent = json.loads(native.column_extents_json()).get(name, [])
            if not extent or not all(v is None or 0 <= v <= 1 for v in extent):
                raise ValueError("progress values must be fractions in [0, 1]")
            yield _range_progress(name, opacity)
            return
        fig._require_data_edit()
        array = _progress_values(values, rows)
        columns = set(fig.data.keys())
        name = artist.id + "/progress"
        index = 1
        while name in columns:
            name = f"{artist.id}/progress/{index}"
            index += 1
        progress = _range_progress(name, opacity)
        native.upload_column(name, array)
        try:
            yield progress
        except BaseException:
            active = artist._spec(fig.get_settings())["render_type"]["RangeBars"].get("progress")
            if active is None or active["column"] != name:
                native.remove_column(name)
            raise


def _range_connector(color, linewidth, dpi):
    from .figure import _color
    from ._validation import number

    return dict(color=_color(color), width=number(linewidth, "connector width") * dpi / 72)


class AdvancedMethods:
    def _sid(self, id=None):
        return _document.identifier(id or f"series_{self.figure._next_series}")

    def _install_series(
        self, specs, columns=(), composites=(), config=None, *, energy_unit=None,
        missing_columns=(),
    ):
        """Publish sources and series together; roll back uncommitted resources."""
        from .figure import _array, Artist

        fig = self.figure
        fig._require_data_edit()
        with fig._lock:
            fig._require_open()
            state = fig.get_settings()
            if state.get("radial"):
                raise ValueError("pie/donut charts require a separate Figure")
            if fig._style_defaults is not None and len(specs) > 1 and any(next(iter(s['render_type'])) in ('CategoryBars','BoxPlot','Radar') for s in specs):
                if _style_runtime._construction(fig)['key'] is not None:
                    raise ValueError('style_key identifies one series; supply explicit colors for a multi-series chart')
            existing = {s["series_id"] for s in state["series"]}
            ids = [s["series_id"] for s in specs]
            if len(set(ids)) != len(ids) or existing.intersection(ids):
                raise ValueError("series IDs must be unique within the Figure")
            identity = None
            if energy_unit:
                identity = state["identity"]
                units = identity.setdefault("energy_units", {})
                owners = {self.subplot_id}
                for group in identity["groups"].values():
                    if group["axis"] == "y" and self.subplot_id in group["members"]:
                        owners.update(group["members"])
                for owner in owners:
                    known = units.get(owner)
                    if known is None:
                        # Older figures recorded the NIST unit in the generated axis title.
                        panel = _document.panel_config(state, owner)
                        title = "".join(s["text"] for s in panel["left_y"]["title_option"]["text"]["segments"])
                        if title.startswith("Energy (") and title.endswith(")"):
                            known = title[len("Energy ("):-1]
                    if known and known.casefold() != energy_unit.casefold():
                        raise ValueError(
                            f"energy axis uses {known!r}, but the NIST data uses {energy_unit!r}"
                        )
                units[self.subplot_id] = energy_unit
            if config is not None:
                local = self._config(state)
                area = copy.deepcopy(local["chart_area"])
                # Existing subplots and overlays belong to this document.
                structural = {
                    k: copy.deepcopy(local[k])
                    for k in ("subplots", "overlays", "annotations")
                    if k in local
                }
                local.clear()
                local.update(copy.deepcopy(config))
                local.update(structural, chart_area=area)
            index = _document.panel_index(state, self.subplot_id)
            if index:
                state["config"]["subplots"][index - 1].setdefault("series", []).extend(
                    ids
                )
            if self.overlay_id:
                self._overlay(state).setdefault("series", []).extend(ids)
            state["config"]["active_layer"] = _document.target_layer(
                state, self.subplot_id, self.overlay_id
            )
            styled_specs = []
            for spec in specs:
                spec, state = _style_runtime.series(fig, state, spec, self.subplot_id)
                styled_specs.append(spec)
            specs = styled_specs
            _document.validate_features(dict(state, series=[*state["series"], *specs]))
            uploaded = []
            try:
                for name, array in columns:
                    fig._native.upload_column(name, _array(array), allow_missing=name in missing_columns)
                    uploaded.append(name)
                for kind, name, fields in composites:
                    normalized = {
                        key: np.ascontiguousarray(
                            value,
                            dtype=(
                                np.uint32
                                if kind == "triangles"
                                else (
                                    np.float32
                                    if np.asarray(value).dtype == np.float32
                                    else np.float64
                                )
                            ),
                        )
                        for key, value in fields.items()
                    }
                    fig._native.upload_composite(kind, name, normalized)
                    uploaded.append(name)
                fig._native.add_series_batch(
                    json.dumps(specs, allow_nan=False),
                    json.dumps(state["config"], allow_nan=False),
                    identity=json.dumps(identity, allow_nan=False) if identity is not None else None,
                )
            except Exception:
                for name in reversed(uploaded):
                    fig._native.remove_column(name)
                raise
            fig._next_series += len(specs)
            _style_runtime._mark_used(fig)
        fig._changed()
        artists = [fig._artist_for(sid) for sid in ids]
        return artists[0] if len(artists) == 1 else artists

    def _projection_config(self, projection):
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        defaults = json.loads(coordinate_defaults_json(projection))
        for key in ("polar", "ternary", "view_3d", "parallel"):
            if key in defaults:
                cfg.setdefault(key, defaults[key])
            else:
                cfg.pop(key, None)
        return cfg

    def set_projection(self, projection="cartesian", **properties):
        if projection == "cartesian":
            state = self.figure.get_settings()
            cfg = self._config(state)
            for key in ("polar", "ternary", "view_3d", "parallel"):
                cfg.pop(key, None)
            self.figure.apply_settings(state)
        else:
            cfg = self._projection_config(projection)
            key = {
                "polar": "polar",
                "ternary": "ternary",
                "3d": "view_3d",
                "parallel": "parallel",
            }[projection]
            cfg[key].update(properties)
            self.configure(**cfg)
        return self

    def stem(
        self,
        x,
        y=None,
        linefmt=None,
        markerfmt=None,
        basefmt=None,
        *,
        bottom=0,
        orientation="vertical",
        color="black",
        label=None,
        id=None,
    ):
        from .figure import _array, _color

        if y is None:
            y = _array(x)
            x = np.arange(y.size, dtype=y.dtype)
        else:
            x, y = _array(x), _array(y)
        if x.size != y.size:
            raise ValueError("x and y must have equal lengths")
        s = template("stem")
        sid = self._sid(id)
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
        style = next(iter(s["render_type"].values()))
        if orientation not in ("vertical", "horizontal"):
            raise ValueError("orientation must be vertical or horizontal")
        style["stem"].update(
            baseline=float(bottom), direction=orientation.title(), color=_color(color)
        )
        style["scatter"]["point_color"] = _color(color)
        from .figure import _LINES, _MARKERS

        if linefmt is not None:
            if linefmt not in _LINES:
                raise ValueError("linefmt must be -, --, : or -.")
            style["stem"]["line_style"] = _LINES[linefmt]
        if markerfmt is not None:
            if markerfmt not in _MARKERS:
                raise ValueError("unsupported markerfmt")
            style["scatter"]["point_shape"] = _MARKERS[markerfmt]
        if basefmt is not None:
            raise ValueError("use axhline/axvline to style the baseline")
        if label is not None:
            from .figure import _segments

            s["label"] = copy.deepcopy(
                self._config(self.figure.get_settings())["legend"]["content"]
            )
            s["label"]["segments"] = _segments(label)
        return self._install_series([s], [(sid + "/x", x), (sid + "/y", y)])

    def streamlines(
        self, x, y, *, color="black", linewidth=1.5, arrows=True, label=None, id=None
    ):
        """Draw precomputed paths, separated by NaN. No integration is hidden here."""
        from .figure import _array, _color

        x, y = _array(x), _array(y)
        if x.size != y.size:
            raise ValueError("path coordinates must have equal lengths")
        sid = self._sid(id)
        s = template("streamlines")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
        body = s["render_type"]["Streamlines"]
        body["line"].update(
            line_color=_color(color), line_width=float(linewidth) * self.figure.dpi / 72
        )
        if not arrows:
            body["arrows"] = None
        if label is not None:
            from .figure import _segments

            s["label"] = copy.deepcopy(
                self._config(self.figure.get_settings())["legend"]["content"]
            )
            s["label"]["segments"] = _segments(label)
        return self._install_series([s], [(sid + "/x", x), (sid + "/y", y)])

    def streamplot(
        self,
        x,
        y,
        u,
        v,
        *,
        density=1,
        start_points=None,
        maxlength=4,
        integration_direction="both",
        color="black",
        linewidth=1.5,
        id=None,
        **kwargs,
    ):
        """Integrate a rectilinear 2-D field on the host, then draw streamlines."""
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        u, v = np.asarray(u), np.asarray(v)
        if (
            x.ndim != 1
            or y.ndim != 1
            or min(x.size, y.size) < 2
            or u.shape != (len(y), len(x))
            or v.shape != u.shape
        ):
            raise ValueError(
                "u/v shape must be (len(y), len(x)) on a 1-D rectilinear grid"
            )
        if np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0):
            raise ValueError("grid coordinates must increase")
        if (
            integration_direction not in ("both", "forward", "backward")
            or not math.isfinite(float(density))
            or density <= 0
        ):
            raise ValueError("invalid integration direction or density")
        if kwargs:
            raise TypeError("unsupported streamplot options: " + ", ".join(kwargs))
        if not math.isfinite(float(maxlength)) or maxlength <= 0:
            raise ValueError("maxlength must be positive and finite")
        nx = max(2, round(12 * density))
        ny = max(2, round(12 * density))
        seeds = (
            np.asarray(start_points, dtype=float)
            if start_points is not None
            else np.stack(
                np.meshgrid(np.linspace(x[0], x[-1], nx), np.linspace(y[0], y[-1], ny)),
                axis=-1,
            ).reshape(-1, 2)
        )
        if seeds.ndim != 2 or seeds.shape[1] != 2:
            raise ValueError("start_points must have shape (N, 2)")
        step = min(np.diff(x).min(), np.diff(y).min()) * 0.35
        limit = max(2, int(float(maxlength) * math.hypot(np.ptp(x), np.ptp(y)) / step))

        def velocity(p):
            px, py = p
            if not (x[0] <= px <= x[-1] and y[0] <= py <= y[-1]):
                return None
            i = min(np.searchsorted(x, px, side="right") - 1, len(x) - 2)
            j = min(np.searchsorted(y, py, side="right") - 1, len(y) - 2)
            tx = (px - x[i]) / (x[i + 1] - x[i])
            ty = (py - y[j]) / (y[j + 1] - y[j])

            def sample(a):
                return (1 - ty) * ((1 - tx) * a[j, i] + tx * a[j, i + 1]) + ty * (
                    (1 - tx) * a[j + 1, i] + tx * a[j + 1, i + 1]
                )

            d = np.array([sample(u), sample(v)])
            norm = np.linalg.norm(d)
            return d / norm if np.isfinite(norm) and norm > 1e-12 else None

        def integrate(seed, direction):
            path = [seed.copy()]
            for _ in range(limit):
                d = velocity(path[-1])
                if d is None:
                    break
                mid = velocity(path[-1] + direction * step * 0.5 * d)
                if mid is None:
                    break
                p = path[-1] + direction * step * mid
                if velocity(p) is None:
                    break
                if len(path) > 12 and np.linalg.norm(p - path[-10]) < step * 0.5:
                    break
                path.append(p)
            return path

        paths = []
        for seed in seeds:
            a = (
                integrate(seed, -1)
                if integration_direction in ("both", "backward")
                else [seed]
            )
            b = (
                integrate(seed, 1)
                if integration_direction in ("both", "forward")
                else [seed]
            )
            path = a[::-1] + b[1:]
            if len(path) > 1:
                paths.extend(path + [[np.nan, np.nan]])
        if not paths:
            raise ValueError("field produces no finite streamline")
        paths = np.asarray(paths)
        return self.streamlines(
            paths[:, 0], paths[:, 1], color=color, linewidth=linewidth, id=id, **kwargs
        )

    def range_bars(
        self,
        positions,
        start,
        end,
        *,
        labels=None,
        orientation=None,
        color=None,
        width=None,
        progress=None,
        remaining_opacity=0.4,
        timeline=False,
        connector=False,
        connector_color=None,
        connector_width=1.0,
        id=None,
    ):
        """Plot intervals, optionally with a Gantt preset and one progress fraction per row."""
        from .figure import _array, _color, _diff, _merge

        positions, start, end = _array(positions), _array(start), _array(end)
        if not positions.size or not positions.size == start.size == end.size:
            raise ValueError("positions/start/end must be nonempty and aligned")
        if orientation is None:
            orientation = "horizontal" if timeline else "vertical"
        if timeline and orientation != "horizontal":
            raise ValueError("timeline bars require horizontal orientation")
        if width is None:
            width = 0.6 if timeline else 0.8
        sid = self._sid(id)
        s = template("timeline_bars" if timeline else "range_bars")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/end")
        body = s["render_type"]["RangeBars"]
        body.update(start=sid + "/start", slot_width=float(width))
        if color is not None:
            body["color"] = _color(color)
            body.pop("color_by", None)
        elif not timeline:
            body["color"] = _color("black")
        if connector:
            body["connector"] = _range_connector(
                tuple(body["color"][key] for key in "rgba") if connector_color is None else connector_color,
                connector_width, self.figure.dpi,
            )
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        if timeline:
            defaults = json.loads(coordinate_defaults_json("cartesian"))
            preset = json.loads(coordinate_defaults_json("timeline"))
            _merge(cfg, _diff(defaults, preset))
        else:
            cfg["bar_groups"] = dict(
                direction=orientation.title(), mode="Grouped", group_width=0.8, bar_gap=2.0
            )
        if labels is not None:
            cfg["bar_groups"]["group_width"] = float(width)
            if len(labels) != len(positions):
                raise ValueError("labels must match positions")
            cfg["left_y" if orientation == "horizontal" else "bottom_x"][
                "categories"
            ] = [dict(id=f"category_{i}", label=str(v)) for i, v in enumerate(labels)]
            body["slot_width"] = None
        columns = [(sid + "/x", positions), (sid + "/start", start), (sid + "/end", end)]
        if progress is not None:
            name = sid + "/progress"
            body["progress"] = _range_progress(name, remaining_opacity)
            columns.append((name, _progress_values(progress, positions.size)))
        return self._install_series([s], columns, config=cfg)

    def broken_barh(self, xranges, yrange, *, color="black", id=None):
        ranges = np.asarray(xranges, dtype=float)
        if ranges.ndim != 2 or ranges.shape[1] != 2:
            raise ValueError("xranges must contain (start, width) pairs")
        return self.range_bars(
            np.full(len(ranges), float(yrange[0]) + float(yrange[1]) / 2),
            ranges[:, 0],
            ranges.sum(axis=1),
            orientation="horizontal",
            width=float(yrange[1]),
            color=color,
            id=id,
        )

    def range_links(
        self, bars, links, *, color=None, width=None, head=None, inset=None, id=None
    ):
        """Connect range-bar rows using zero-based (predecessor, successor) pairs.

        Pass the range-bar artist or its ID. Link mappings can specify ``from``,
        ``to``, and ``exit_fraction`` (0 at the predecessor start, 1 at its end).
        Width, head and inset use points. The beta ``exit_offset`` in points
        is converted using the current predecessor bar length.
        Use the returned artist's ``set(links=...)`` to replace the connections.
        """
        from .figure import _color
        from ._validation import number

        parent = getattr(bars, "id", bars)
        with self.figure._lock:
            state = self.figure.get_settings()
            series = self._owned_series(state)
            if getattr(bars, "figure", self.figure) is not self.figure or not any(
                s["series_id"] == parent and "RangeBars" in s["render_type"]
                for s in series
            ):
                raise ValueError("bars must name a range-bar series on these axes")
            spec = template("range_links")
            spec["series_id"] = self._sid(id)
            body = spec["render_type"]["RangeLinks"]
            body.update(bars=parent, links=_range_link_rows(links, self.figure.dpi))
            if color is not None:
                body["color"] = _color(color)
            for key, value in (("width", width), ("head", head), ("inset", inset)):
                if value is not None:
                    body[key] = number(value, key) * self.figure.dpi / 72
            candidate = dict(config=state["config"], series=[*state["series"], spec])
            spec = self.figure._migrate_range_links(candidate)["series"][-1]
            return self._install_series([spec])

    def set_line_offsets(self, series=None, *, x=0, y=0):
        """Stack line series by steps in data units, or decades on log axes."""
        if self.overlay_id:
            raise ValueError("line offsets belong to a panel, not an overlay")
        with self.figure._lock:
            state = self.figure.get_settings()
            config = self._config(state)
            if series is None:
                config.pop("line_offsets", None)
            else:
                config["line_offsets"] = {
                    "series": [getattr(item, "id", item) for item in series],
                    "step_x": float(x),
                    "step_y": float(y),
                }
            self.figure.apply_settings(state)
        return self

    def waterfall(self, labels, values, *, color="black", connector=True,
                  connector_color=None, connector_width=1.0, id=None):
        """Draw cumulative steps and join adjacent bars with a connector in points."""
        values = np.asarray(values)
        end = np.cumsum(values)
        start = end - values
        return self.range_bars(
            np.arange(len(values)), start, end, labels=labels, color=color, id=id,
            connector=connector, connector_color=connector_color, connector_width=connector_width,
        )

    def candlestick(
        self, x, open, high, low, close, *, width=0.7, color="black", id=None
    ):
        # Range bodies plus the renderer's own whisker columns.
        from .figure import _array, _color

        sid = self._sid(id)
        s = template("range_bars")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/close")
        b = s["render_type"]["RangeBars"]
        b.update(
            start=sid + "/open",
            color=_color(color),
            slot_width=float(width),
            whiskers=dict(
                low=sid + "/low", high=sid + "/high", width=self.figure.dpi / 72
            ),
        )
        arrays = [_array(v) for v in (x, open, high, low, close)]
        if len({len(a) for a in arrays}) != 1:
            raise ValueError("OHLC columns must be aligned")
        return self._install_series(
            [s],
            [
                (sid + "/" + name, a)
                for name, a in zip(("x", "open", "high", "low", "close"), arrays)
            ],
        )

    def ternary(self, a, b, c, *, color="black", label=None, id=None):
        from .figure import _array, _color

        a, b, c = map(_array, (a, b, c))
        if not a.size or not a.size == b.size == c.size:
            raise ValueError("ternary components must be nonempty and aligned")
        sid = self._sid(id)
        s = template("ternary")
        s.update(series_id=sid, x_column=sid + "/a", y_column=sid + "/b")
        body = s["render_type"]["Ternary"]
        body["c_column"] = sid + "/c"
        body["scatter"]["point_color"] = _color(color)
        if label is not None:
            from .figure import _segments

            s["label"] = copy.deepcopy(
                self._config(self.figure.get_settings())["legend"]["content"]
            )
            s["label"]["segments"] = _segments(label)
        return self._install_series(
            [s],
            [(sid + "/a", a), (sid + "/b", b), (sid + "/c", c)],
            config=self._projection_config("ternary"),
        )

    def parallel_coordinates(
        self, values, *, labels=None, color="black", linewidth=1, id=None
    ):
        from .figure import _color

        a = np.asarray(values)
        if a.ndim != 2 or a.shape[1] < 2 or not len(a):
            raise ValueError(
                "values must be a nonempty rows-by-axes matrix with at least two axes"
            )
        labels = (
            list(labels)
            if labels is not None
            else [f"Axis {i+1}" for i in range(a.shape[1])]
        )
        if len(labels) != a.shape[1]:
            raise ValueError("labels must match axes")
        sid = self._sid(id)
        names = [sid + f"/axis/{i}" for i in range(a.shape[1])]
        s = template("parallel")
        s.update(series_id=sid, x_column=names[0], y_column=names[1])
        body = s["render_type"]["Parallel"]
        body["columns"] = names
        body["line"].update(
            line_color=_color(color), line_width=float(linewidth) * self.figure.dpi / 72
        )
        cfg = self._projection_config("parallel")
        cfg["bottom_x"]["categories"] = [
            dict(id=f"axis_{i}", label=str(v)) for i, v in enumerate(labels)
        ]
        axes = []
        for column in a.T:
            finite = column[np.isfinite(column)]
            if not finite.size:
                raise ValueError("each parallel axis needs finite data")
            low, high = float(finite.min()), float(finite.max())
            pad = (high - low) * 0.05 if high > low else max(abs(low) * 0.05, 1.0)
            axes.append(dict(min=low - pad, max=high + pad))
        cfg["parallel"]["axes"] = axes
        return self._install_series([s], list(zip(names, a.T)), config=cfg)

    def tripcolor(
        self,
        x,
        y,
        c,
        *,
        triangles,
        shading="gouraud",
        cmap="viridis",
        vmin=None,
        vmax=None,
        id=None,
    ):
        return self._tri_mesh(
            x, y, c, triangles, shading=shading, cmap=cmap, vmin=vmin, vmax=vmax, id=id
        )

    def _tri_mesh(
        self, x, y, c, triangles, *, cmap, id, shading="gouraud", vmin=None,
        vmax=None, contour=None, filled=False,
    ):
        from .figure import _array
        from ._features import colorbar

        x, y, c = map(_array, (x, y, c))
        tri = np.asarray(triangles)
        if (
            tri.ndim != 2
            or tri.shape[1] != 3
            or not len(tri)
            or not np.issubdtype(tri.dtype, np.integer)
            or tri.min() < 0
            or tri.max() >= len(x)
        ):
            raise ValueError("triangles must contain valid integer vertex triples")
        if len(x) != len(y):
            raise ValueError("vertex coordinates must align")
        if shading not in ("gouraud", "interpolated", "flat"):
            raise ValueError("shading must be gouraud or flat")
        at = "Vertices" if shading in ("gouraud", "interpolated") else "Faces"
        if len(c) != (len(x) if at == "Vertices" else len(tri)):
            raise ValueError("color values must match vertices or faces for shading")
        sid = self._sid(id)
        s = template("tri_mesh")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
        body = s["render_type"]["TriMesh"]
        body["triangles"] = sid + "/triangles"
        body["values"] = dict(column=sid + "/values", at=at)
        body["fill"]["shading"] = "Interpolated" if at == "Vertices" else "Flat"
        if contour is not None:
            body["contour"] = contour
            body["fill"] = (
                dict(mode="Bands", shading="Interpolated", opacity=1.0) if filled else None
            )
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        colorbar(cfg, c, cmap, vmin, vmax)
        return self._install_series(
            [s],
            [(sid + "/x", x), (sid + "/y", y), (sid + "/values", c)],
            [("triangles", sid + "/triangles", dict(indices=tri.reshape(-1)))],
            config=cfg,
        )

    def tricontour(
        self,
        x,
        y,
        z,
        levels=8,
        *,
        triangles,
        colors="black",
        linewidths=1.5,
        cmap="viridis",
        filled=False,
        id=None,
    ):
        from .figure import _array, _color

        z = _array(z)
        finite = z[np.isfinite(z)]
        if not finite.size:
            raise ValueError("z needs finite values")
        if isinstance(levels, (int, np.integer)):
            if not 1 <= levels <= 1024:
                raise ValueError("levels must be 1..1024")
            low, high = float(finite.min()), float(finite.max())
            if low == high:
                high = low + 1
            levels = np.linspace(low, high, int(levels) + 2)[1:-1]
        levels = _array(levels)
        if (
            not 1 <= len(levels) <= 1024
            or not np.isfinite(levels).all()
            or not np.all(np.diff(levels) > 0)
        ):
            raise ValueError("levels must be finite and strictly increasing")
        line = dict(
            line_style="Solid",
            line_color=_color(colors),
            line_width=float(linewidths) * self.figure.dpi / 72,
        )
        if not math.isfinite(line["line_width"]) or line["line_width"] < 0:
            raise ValueError("linewidths must be finite and nonnegative")
        return self._tri_mesh(
            x, y, z, triangles, cmap=cmap, id=id,
            contour=dict(levels=levels.tolist(), line=line), filled=filled,
        )

    def tricontourf(self, x, y, z, levels=8, **kwargs):
        kwargs.setdefault("linewidths", 0.0)
        return self.tricontour(x, y, z, levels, filled=True, **kwargs)

    def plot_trisurf(self, x, y, z, *, triangles, cmap="viridis", id=None, **kwargs):
        # Mesh heights and colours may share one uploaded column.
        from .figure import _array
        from ._features import colorbar

        x, y, z = map(_array, (x, y, z))
        tri = np.asarray(triangles)
        if (
            not len(x) == len(y) == len(z)
            or tri.ndim != 2
            or tri.shape[1] != 3
            or not np.issubdtype(tri.dtype, np.integer)
            or tri.min() < 0
            or tri.max() >= len(x)
        ):
            raise ValueError("invalid mesh coordinates or triangles")
        sid = self._sid(id)
        s = template("tri_mesh")
        s.update(
            series_id=sid, x_column=sid + "/x", y_column=sid + "/y", z_column=sid + "/z"
        )
        b = s["render_type"]["TriMesh"]
        b["triangles"] = sid + "/triangles"
        b["values"] = dict(column=sid + "/z", at="Vertices")
        b["fill"]["shading"] = "Interpolated"
        cfg = self._projection_config("3d")
        colorbar(cfg, z, cmap, kwargs.pop("vmin", None), kwargs.pop("vmax", None))
        if kwargs:
            raise TypeError("unknown trisurf options: " + ", ".join(kwargs))
        return self._install_series(
            [s],
            [(sid + "/x", x), (sid + "/y", y), (sid + "/z", z)],
            [("triangles", sid + "/triangles", dict(indices=tri.reshape(-1)))],
            config=cfg,
        )

    def energy_levels(
        self,
        levels,
        *,
        transitions=(),
        limits=(),
        bands=(),
        show="main",
        wavelength_labels=False,
        id=None,
        **style,
    ):
        """Draw row records or a read_nist() result, retaining spectroscopic metadata."""
        from ._diagram_input import records, plain, require
        from ._nist import NistData

        if isinstance(levels, NistData):
            if len(transitions) or len(limits):
                raise ValueError("NIST data already supplies transitions and limits")
            data = levels
            levels, transitions, limits = data.levels, data.transitions, data.limits
            energy_unit = data.energy_unit.strip()
        else:
            energy_unit = None
        state = self.figure.get_settings()
        cfg = copy.deepcopy(self._config(state))
        rich = cfg["legend"]["content"]
        levels = records(levels, "levels", rich, dpi=self.figure.dpi)
        transitions = records(transitions, "transitions", rich, dpi=self.figure.dpi)
        limits = records(limits, "limits", rich, dpi=self.figure.dpi)
        level_ids = require(levels, ("id", "column", "energy"), "levels")
        require(limits, ("id", "energy"), "limits")
        require(transitions, ("id", "lower", "upper"), "transitions")
        for transition in transitions:
            if (
                transition["lower"] not in level_ids
                or transition["upper"] not in level_ids
            ):
                raise ValueError("transition endpoints must name existing level IDs")
        for level in levels:
            if not isinstance(level["column"], str) or not level["column"]:
                raise ValueError("level.column must be a nonempty string")
        sid = self._sid(id)
        s = template("energy_levels")
        s["series_id"] = sid
        body = s["render_type"]["EnergyLevels"]
        body.update(levels=levels, transitions=transitions, limits=limits)
        if len(bands):
            body["bands"] = records(bands, "bands", rich, dpi=self.figure.dpi)
        body["show"] = {"main": "Main", "components": "Components"}.get(show, show)
        _diagram_style_update(body["style"], plain(style))
        from ._diagram_artist import _set_wavelength_labels

        _set_wavelength_labels(body["style"], wavelength_labels, self.figure)
        new_energies = np.asarray(
            [row["energy"] for row in [*levels, *limits]], dtype=float
        )
        if not new_energies.size or not np.isfinite(new_energies).all():
            raise ValueError("energy levels need finite energies")
        categories = {row["id"]: row for row in cfg["bottom_x"].get("categories") or []}
        energy_series = {
            spec["series_id"]: spec["render_type"]["EnergyLevels"]
            for spec in state["series"]
            if "EnergyLevels" in spec["render_type"]
        }
        energies = list(new_energies)
        for spec in self.figure.subplots[self.subplot_id].axes._owned_series(state):
            existing = energy_series.get(spec["series_id"])
            if existing is None:
                continue
            if existing.get("source") is not None:
                existing = energy_series.get(existing["source"], existing)
            for row in existing.get("levels", []):
                column = row["column"]
                categories.setdefault(column, dict(id=column, label=column))
                energies.append(row["energy"])
            energies.extend(row["energy"] for row in existing.get("limits", []))
        for row in levels:
            column = row["column"]
            categories.setdefault(column, dict(id=column, label=column))
        cfg["bottom_x"]["categories"] = list(categories.values())
        low, high = float(min(energies)), float(max(energies))
        padding = (high - low) * 0.05 if high > low else max(abs(low) * 0.05, 1.0)
        for axis in ("left_y", "right_y"):
            cfg[axis].update(
                min=low - padding,
                max=high + padding,
                major_spacing=(high - low + 2 * padding) / 5,
            )
            if energy_unit and not state["identity"].get("energy_units", {}).get(self.subplot_id):
                from .figure import _segments

                cfg[axis]["title_option"]["text"]["segments"] = _segments(
                    "Energy (" + energy_unit + ")"
                )
                cfg[axis]["title_option"]["visible"] = True
        return self._install_series([s], config=cfg, energy_unit=energy_unit)

    def feynman(
        self, vertices, propagators, *, layout=None, direction=None, id=None, **style
    ):
        """Draw a topology; omitted vertex positions use the renderer's automatic layout."""
        from ._diagram_input import records, plain, require

        rich = self._config(self.figure.get_settings())["legend"]["content"]
        vertices = records(vertices, "vertices", rich, dpi=self.figure.dpi)
        propagators = records(propagators, "propagators", rich, dpi=self.figure.dpi)
        vertex_ids = require(vertices, ("id",), "vertices")
        require(propagators, ("id", "from", "to", "particle"), "propagators")
        for edge in propagators:
            if edge["from"] not in vertex_ids or edge["to"] not in vertex_ids:
                raise ValueError("propagator endpoints must name existing vertex IDs")
        if direction is not None and layout is not None:
            raise ValueError("supply direction or layout, not both")
        if direction is not None:
            layout = dict(
                direction={
                    "left-to-right": "LeftToRight",
                    "bottom-to-top": "BottomToTop",
                }.get(direction, direction)
            )
        sid = self._sid(id)
        s = template("feynman")
        s["series_id"] = sid
        body = s["render_type"]["Feynman"]
        body.update(vertices=vertices, propagators=propagators)
        if layout is not None:
            body["layout"] = plain(layout)
        _diagram_style_update(body["style"], plain(style))
        return self._install_series([s])

    def view_init(self, elev=30, azim=-60, *, projection=None):
        cfg = self._projection_config("3d")
        cfg["view_3d"].update(
            elevation_degrees=float(elev), azimuth_degrees=float(azim)
        )
        if projection is not None:
            cfg["view_3d"]["projection"] = {
                "ortho": "Orthographic",
                "persp": "Perspective",
            }.get(projection, projection)
        return self.configure(**cfg)

    def _install_legacy_chart(self, kind, chart):
        from ._native import convert_legacy_chart_json

        # Legacy documents cap a shared label font at 32px. Use their public
        # data conversion, then restore the requested size on common axes.
        font_size = float(chart['font_size'])
        if not math.isfinite(font_size) or font_size <= 0:
            raise ValueError('font_size must be positive and finite')
        wire = dict(chart, font_size=min(32., max(8., font_size)))
        bundle = json.loads(
            convert_legacy_chart_json(kind, json.dumps(wire, allow_nan=False))
        )
        if wire['font_size'] != font_size:
            for side in ('bottom_x','top_x','left_y','right_y'):
                bundle['config'][side]['label_style']['font_size'] = font_size
                bundle['config'][side]['title_option']['text']['font_size'] = font_size
            bundle['config']['legend']['content']['font_size'] = font_size
            for spec in bundle['series']:
                if spec.get('label') is not None:spec['label']['font_size'] = font_size
        prefix = f"chart/{self.figure._next_series}/"
        remap = {
            s["series_id"]: self._sid() + f"/{i}"
            for i, s in enumerate(bundle["series"])
        }
        remap.update({u["id"]: prefix + u["id"] for u in bundle["uploads"]})

        def rename(v, key=""):
            if isinstance(v, dict):
                return {k: rename(x, k) for k, x in v.items()}
            if isinstance(v, list):
                return [rename(x, key) for x in v]
            if isinstance(v, str) and key not in ("text", "label", "font"):
                return remap.get(v, v)
            return v

        specs = [rename(s) for s in bundle["series"]]
        cfg = rename(bundle["config"])
        area = chart.get("decorations", {}).get("data_area")
        if area is not None:
            cfg["layout_state"] = "fixed"
            canvas = self._config(self.figure.get_settings())["chart_area"]
            for axis, margin in (
                ("left_y", area["x"] - canvas["x"]),
                ("top_x", area["y"] - canvas["y"]),
                ("right_y", canvas["x"] + canvas["width"] - area["x"] - area["width"]),
                (
                    "bottom_x",
                    canvas["y"] + canvas["height"] - area["y"] - area["height"],
                ),
            ):
                cfg[axis]["out_margin"] = margin
            cfg["chart_title"]["top_margin"] = 0

        columns = []
        composites = []
        for upload in bundle["uploads"]:
            name = remap[upload["id"]]
            if upload["kind"] == "column":
                columns.append((name, np.asarray(upload["data"], dtype=np.float64)))
            else:
                composites.append(
                    (
                        upload["kind"],
                        name,
                        {
                            k: np.asarray(v, dtype=np.float64)
                            for k, v in upload["data"].items()
                        },
                    )
                )
        artists = self._install_series(specs, columns, composites, config=cfg)
        if chart.get("value_range") is not None:
            axis = "x" if chart.get("direction") == "Horizontal" else "y"
            getattr(self, "set_" + axis + "lim")(*chart["value_range"])
        return artists

    def bar(
        self,
        x,
        height,
        width=0.8,
        bottom=None,
        *,
        align="center",
        label=None,
        colors=None,
        color=None,
        mode="grouped",
        orientation="vertical",
        **properties,
    ):
        return self._category_bars(
            x, height, width, bottom, align=align, label=label, colors=colors,
            color=color, mode=mode, orientation=orientation, properties=properties,
        )

    def _category_bars(
        self, x, height, width=0.8, bottom=None, *, align="center", label=None,
        colors=None, color=None, mode="grouped", orientation="vertical",
        projection=None, properties=None,
    ):
        from .figure import _color, _COLORS

        properties = {} if properties is None else properties
        style_patch = properties.pop("style", {})
        if not isinstance(style_patch, dict):raise TypeError("style must be a mapping")
        if properties:
            if projection is not None:
                raise TypeError(f"unsupported rose options: {', '.join(sorted(properties))}")
            from ._charts import ChartMethods

            return ChartMethods.bar(
                self,
                x,
                height,
                label=label,
                colors=colors,
                color=color,
                mode=mode,
                orientation=orientation,
                style=style_patch,
                **properties,
            )
        values = np.asarray(height)
        if values.dtype == object:
            values = np.asarray(
                [
                    [np.nan if v is None else v for v in row]
                    for row in (values[None, :] if values.ndim == 1 else values)
                ]
            )
        if values.ndim == 1:
            values = values[None, :]
        labels = list(x)
        if values.ndim != 2 or values.shape[1] != len(labels) or not len(labels):
            raise ValueError("height must have one value per category")
        if bottom is not None:
            raise ValueError(
                'use range_bars for floating bars or mode="stacked" for stacks'
            )
        if align != "center":
            raise ValueError('category bars support align="center"')
        if orientation not in ("vertical", "horizontal") or mode not in (
            "grouped",
            "stacked",
            "percent_stacked",
        ):
            raise ValueError("invalid bar orientation or mode")
        cfg = projection if projection is not None else copy.deepcopy(self._config(self.figure.get_settings()))
        axis = "bottom_x" if orientation == "vertical" else "left_y"
        cfg[axis]["categories"] = [
            dict(id=f"category_{i}", label=str(v)) for i, v in enumerate(labels)
        ]
        cfg["bar_groups"] = dict(
            mode={
                "grouped": "Grouped",
                "stacked": "Stacked",
                "percent_stacked": "PercentStacked",
            }[mode],
            direction=orientation.title(),
            group_width=float(width),
            bar_gap=2.0,
        )
        specs = []
        columns = []
        names = (
            [label]
            if isinstance(label, str)
            else list(label) if label is not None else [None] * len(values)
        )
        palette = (
            list(colors)
            if colors is not None
            else [
                color or _COLORS[(self.figure._next_series + i) % len(_COLORS)]
                for i in range(len(values))
            ]
        )
        if len(names) != len(values) or len(palette) != len(values):
            raise ValueError("label/colors must match series count")
        for i, row in enumerate(values):
            sid = f"series_{self.figure._next_series+i}"
            s = template("category_bars")
            s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
            b = s["render_type"]["CategoryBars"]
            b["color"] = _color(palette[i])
            _style_update(b["style"], style_patch)
            if names[i] is not None:
                from .figure import _segments

                s["label"] = copy.deepcopy(cfg["legend"]["content"])
                s["label"]["segments"] = _segments(names[i])
            p = np.arange(len(labels), dtype=np.float32)
            columns.extend(
                [
                    (sid + "/x", p if orientation == "vertical" else row),
                    (sid + "/y", row if orientation == "vertical" else p),
                ]
            )
            specs.append(s)
        return self._install_series(specs, columns, config=cfg)

    def radar(self, categories, values, *, labels=None, colors=None, **properties):
        from .figure import _color, _COLORS, _segments

        style_patch = properties.pop("style", {})
        if not isinstance(style_patch, dict):raise TypeError("style must be a mapping")
        if set(properties) - {"value_range"}:
            from ._features import FeatureMethods

            return FeatureMethods.radar(
                self, categories, values, labels=labels, colors=colors, style=style_patch, **properties
            )
        bounds = properties.get("value_range")
        if bounds is not None:
            from ._validation import number

            low, high = (number(v, "radar value range") for v in bounds)
            if low >= high:
                raise ValueError("radar value range must be increasing")
            bounds = (low, high)
        categories = list(categories)
        a = np.asarray(values)
        if a.ndim == 1:
            a = a[None, :]
        if a.ndim != 2 or a.shape[1] != len(categories) or not np.isfinite(a).all():
            raise ValueError("values must be a finite series-by-category matrix")
        labels = (
            list(labels)
            if labels is not None
            else [f"Series {i+1}" for i in range(len(a))]
        )
        colors = (
            list(colors)
            if colors is not None
            else [_COLORS[i % len(_COLORS)] for i in range(len(a))]
        )
        if len(labels) != len(a) or len(colors) != len(a):
            raise ValueError("labels/colors must match series count")
        cfg = self._projection_config("polar")
        cfg["polar"].update(
            zero_angle_degrees=90.0,
            angle_unit="Degrees",
            grid_shape="Polygon",
        )
        cfg["bottom_x"]["categories"] = [
            dict(id=f"category_{i}", label=str(v)) for i, v in enumerate(categories)
        ]
        specs = []
        columns = []
        for i, row in enumerate(a):
            sid = f"series_{self.figure._next_series+i}"
            s = template("radar")
            s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
            s["render_type"]["Radar"]["color"] = _color(colors[i])
            s["label"] = copy.deepcopy(cfg["legend"]["content"])
            s["label"]["segments"] = _segments(labels[i])
            s["render_type"]["Radar"]["style"].setdefault("fill_opacity", None)
            _style_update(s["render_type"]["Radar"]["style"], style_patch)
            specs.append(s)
            columns.extend(
                [
                    (sid + "/x", np.arange(len(categories), dtype=np.float32)),
                    (sid + "/y", row),
                ]
            )
        artists = self._install_series(specs, columns, config=cfg)
        if bounds is not None:
            self.set_ylim(*bounds)
        return artists

    def rose(self, categories, values, **kwargs):
        kwargs = dict(kwargs)
        style = kwargs.pop("style", {})
        cfg = self._projection_config("polar")
        return self._category_bars(categories, values, projection=cfg, properties={"style": style}, **kwargs)

    def violinplot(
        self,
        dataset,
        positions=None,
        *,
        vert=True,
        orientation=None,
        widths=0.5,
        showmeans=False,
        showmedians=False,
        showextrema=True,
        bw_method=None,
        points=100,
        side="both",
        color="blue",
        raw_points=False,
        id=None,
    ):
        from .figure import _color

        rows = _rows(dataset)
        n = len(rows)
        if not n or points < 2:
            raise ValueError("violinplot needs samples and at least two curve points")
        if positions is not None and not np.array_equal(
            np.asarray(positions), np.arange(1, n + 1)
        ):
            raise ValueError("categorical violin positions must be 1..N")
        if side not in ("both", "low", "high"):
            raise ValueError("side must be both, low or high")
        if showmeans or showmedians or showextrema:
            # Show the statistics through the same box record as boxplot.
            summaries = []
            for row in rows:
                a = np.asarray(row, dtype=float)
                if a.ndim != 1 or not a.size or not np.isfinite(a).all():
                    raise ValueError("each violin needs finite one-dimensional samples")
                q1, med, q3 = np.percentile(a, [25, 50, 75])
                summaries.append(
                    dict(
                        median=med,
                        q1=q1,
                        q3=q3,
                        whisker_low=a.min(),
                        whisker_high=a.max(),
                        mean=a.mean(),
                    )
                )
        else:
            summaries = None
        sid = self._sid(id)
        s = template("box_plot")
        s.update(
            series_id=sid,
            x_column=sid + "/positions",
            y_column=sid + "/record" if summaries else "",
        )
        b = s["render_type"]["BoxPlot"]
        b["color"] = _color(color)
        b["style"]["show_mean"] = bool(showmeans)
        if not showmedians:
            b["style"]["median_width"] = 0.0
        if not showextrema:
            b["style"]["whisker_width"] = 0.0
            b["style"]["caps"] = False
        curve = []
        density = []
        offsets = [0]
        for row in rows:
            a = np.asarray(row, dtype=float)
            if a.ndim != 1 or not a.size or not np.isfinite(a).all():
                raise ValueError("each violin needs finite one-dimensional samples")
            if bw_method is None or bw_method == "scott":
                factor = len(a) ** (-0.2)
            elif bw_method == "silverman":
                factor = (len(a) * 0.75) ** (-0.2)
            elif np.isscalar(bw_method):
                factor = float(bw_method)
            else:
                raise ValueError(
                    "bw_method must be scott, silverman or a positive factor"
                )
            bandwidth = float(np.std(a, ddof=1)) * factor if len(a) > 1 else 0.0
            bandwidth = max(bandwidth, max(abs(float(a.mean())), 1.0) * 1e-6)
            if not math.isfinite(bandwidth) or bandwidth <= 0:
                raise ValueError("invalid bandwidth")
            grid = np.linspace(
                a.min() - bandwidth * 2, a.max() + bandwidth * 2, int(points)
            )
            d = np.zeros(len(grid))
            for begin in range(0, len(a), 4096):
                d += np.exp(
                    -0.5
                    * ((grid[:, None] - a[None, begin : begin + 4096]) / bandwidth) ** 2
                ).sum(axis=1)
            d /= len(a) * bandwidth * math.sqrt(2 * math.pi)
            d /= d.max()
            curve.extend(grid)
            density.extend(d)
            offsets.append(len(curve))
        half = dict(
            curve=sid + "/curve", density=sid + "/density", density_scale=1.0, style={}
        )
        b["violin"] = dict(
            body={"Symmetric": half} if side == "both" else {"Split": {side: half}},
            box_width=0.25 if summaries else 0.0,
        )
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        direction = orientation or ("vertical" if vert else "horizontal")
        cfg["bar_groups"] = dict(
            mode="Grouped",
            direction=direction.title(),
            group_width=float(widths),
            bar_gap=2.0,
        )
        cfg["bottom_x" if direction == "vertical" else "left_y"]["categories"] = [
            dict(id=f"category_{i}", label=str(i + 1)) for i in range(n)
        ]
        columns = [
            (sid + "/positions", np.arange(n, dtype=np.float32)),
            (sid + "/density", density),
        ]
        composites = [("ragged", sid + "/curve", dict(values=curve, offsets=offsets))]
        if summaries:
            composites.append(
                (
                    "record",
                    sid + "/record",
                    {k: np.array([r[k] for r in summaries]) for k in summaries[0]},
                )
            )
        if raw_points:
            columns.extend(
                [
                    (
                        sid + "/raw_positions",
                        np.concatenate(
                            [
                                np.full(len(r), i, dtype=np.float32)
                                for i, r in enumerate(rows)
                            ]
                        ),
                    ),
                    (sid + "/raw_values", np.concatenate(rows)),
                ]
            )
            b["points"] = dict(
                positions=sid + "/raw_positions", values=sid + "/raw_values", style={}
            )
        return self._install_series([s], columns, composites, config=cfg)

    def raincloud(self, dataset, **kwargs):
        return self.violinplot(dataset, side="low", raw_points=True, **kwargs)

    def imshow_rgb(
        self, image, *, extent=None, origin="upper", interpolation="nearest", id=None
    ):
        a = np.asarray(image)
        if a.ndim != 3 or a.shape[2] not in (3, 4) or not a.shape[0] or not a.shape[1]:
            raise ValueError("RGB(A) image must have shape (rows, columns, 3 or 4)")
        if a.shape[2] == 4:
            raise ValueError(
                "renderer RGB images do not accept a per-pixel alpha channel"
            )
        if origin not in ("upper", "lower"):
            raise ValueError("origin must be upper or lower")
        sid = self._sid(id)
        s = template("rgb_image")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
        b = s["render_type"]["RgbImage"]
        b["range"] = [0.0, 255.0] if a.dtype == np.uint8 else [0.0, 1.0]
        b["shading"] = (
            "Flat" if interpolation in ("nearest", "none") else "Interpolated"
        )
        rows, cols = a.shape[:2]
        left, right, bottom, top = (
            extent if extent is not None else (-0.5, cols - 0.5, -0.5, rows - 0.5)
        )
        columns = [
            (sid + "/x", np.linspace(left, right, cols + 1)),
            (sid + "/y", np.linspace(bottom, top, rows + 1)),
        ]
        for channel, key in enumerate(("red", "green", "blue")):
            names = [sid + f"/{key}/{row}" for row in range(rows)]
            b[key] = dict(columns=names, orientation="ColumnsAreY", grid_layout="Edges")
            columns.extend(zip(names, a[:, :, channel]))
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        cfg["left_y"]["inverted"] = origin == "upper"
        return self._install_series([s], columns, config=cfg)

    def hexbin(
        self,
        x,
        y,
        C=None,
        *,
        gridsize=30,
        extent=None,
        reduce_C_function=np.mean,
        mincnt=None,
        cmap="viridis",
        vmin=None,
        vmax=None,
        id=None,
    ):
        """Bin finite samples, ignoring points outside an explicit extent."""
        from ._features import colorbar

        x, y = np.asarray(x), np.asarray(y)
        if x.ndim != 1 or y.shape != x.shape or not x.size:
            raise ValueError("x/y must be aligned one-dimensional samples")
        valid = np.isfinite(x) & np.isfinite(y)
        if C is not None:
            C = np.asarray(C)
            if C.shape != x.shape:
                raise ValueError("C must match x/y")
            valid &= np.isfinite(C)
        if extent is not None:
            extent = tuple(map(float, extent))
            if (
                len(extent) != 4
                or not all(map(math.isfinite, extent))
                or extent[0] >= extent[1]
                or extent[2] >= extent[3]
            ):
                raise ValueError("extent requires increasing finite x/y bounds")
            xmin, xmax, ymin, ymax = extent
            valid &= (xmin <= x) & (x <= xmax) & (ymin <= y) & (y <= ymax)
        if C is not None:
            C = C[valid]
        x, y = x[valid], y[valid]
        if not x.size:
            if extent is not None:
                raise ValueError("hexbin requires finite samples within extent")
            raise ValueError("hexbin requires finite samples")
        nx, ny = (
            (int(gridsize), max(2, round(int(gridsize) / math.sqrt(3))))
            if np.isscalar(gridsize)
            else map(int, gridsize)
        )
        if min(nx, ny) < 2:
            raise ValueError("gridsize must be at least two per axis")
        xmin, xmax, ymin, ymax = (
            extent
            if extent is not None
            else (float(x.min()), float(x.max()), float(y.min()), float(y.max()))
        )
        if xmin == xmax:
            xmax = xmin + 1
        if ymin == ymax:
            ymax = ymin + 1
        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        dx = xs[1] - xs[0]
        dy = ys[1] - ys[0]
        # The renderer's flat-topped lattice raises odd columns by half a row.
        xf = (x - xmin) / dx
        i0 = np.clip(np.floor(xf).astype(int), 0, nx - 1)
        i1 = np.clip(i0 + 1, 0, nx - 1)

        def candidate(i):
            j = np.clip(np.rint((y - ymin) / dy - (i % 2) * 0.5).astype(int), 0, ny - 1)
            distance = (1.5 * (x - xs[i]) / dx) ** 2 + (
                math.sqrt(3) * (y - (ys[j] + (i % 2) * dy * 0.5)) / dy
            ) ** 2
            return j, distance

        j0, d0 = candidate(i0)
        j1, d1 = candidate(i1)
        choose = d1 < d0
        i = np.where(choose, i1, i0)
        j = np.where(choose, j1, j0)
        z = np.full((ny, nx), np.nan)
        flat = j * nx + i
        if C is None:
            counts = np.bincount(flat, minlength=nx * ny).reshape(ny, nx)
            z[:] = counts
            z[counts < (1 if mincnt is None else mincnt)] = np.nan
        else:
            for cell in np.unique(flat):
                vals = C[flat == cell]
                if len(vals) >= (1 if mincnt is None else mincnt):
                    z.flat[cell] = reduce_C_function(vals)
        sid = self._sid(id)
        s = template("hexbin")
        s.update(series_id=sid, x_column=sid + "/x", y_column=sid + "/y")
        body = next(iter(s["render_type"].values()))
        names = [sid + f"/z/{r}" for r in range(ny)]
        body["matrix"] = dict(
            columns=names, orientation="ColumnsAreY", grid_layout="Hexagonal"
        )
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        colorbar(cfg, z, cmap, vmin, vmax)
        return self._install_series(
            [s], [(sid + "/x", xs), (sid + "/y", ys), *zip(names, z)],
            config=cfg, missing_columns=set(names),
        )

    def plot_surface(
        self, X, Y, Z, *, cmap="viridis", vmin=None, vmax=None, id=None, **style
    ):
        from ._features import colorbar

        x, y, z = np.asarray(X), np.asarray(Y), np.asarray(Z)
        if x.ndim == 2 and y.ndim == 2:
            if (
                x.shape != z.shape
                or y.shape != z.shape
                or not np.allclose(x, x[0, :][None, :])
                or not np.allclose(y, y[:, 0][:, None])
            ):
                raise ValueError(
                    "surface X/Y must describe a rectilinear meshgrid; use plot_trisurf for other meshes"
                )
            x, y = x[0, :], y[:, 0]
        if x.ndim != 1 or y.ndim != 1 or z.shape != (len(y), len(x)):
            raise ValueError("Z shape must be (len(Y), len(X))")
        sid = self._sid(id)
        names = [sid + f"/z/{i}" for i in range(len(y))]
        # Use an existing accepted heatmap model, then enable its surface look.
        surface = template("surface_style")
        _style_update(surface, style)
        b = dict(
            matrix=dict(
                columns=names, orientation="ColumnsAreY", grid_layout="Centers"
            ),
            fill=dict(mode="Continuous", shading="Interpolated", opacity=1.0),
            surface=surface,
        )
        s = dict(
            series_id=sid,
            label=None,
            x_column=sid + "/x",
            y_column=sid + "/y",
            render_type={"Heatmap": b},
        )
        cfg = self._projection_config("3d")
        colorbar(cfg, z, cmap, vmin, vmax)
        return self._install_series(
            [s], [(sid + "/x", x), (sid + "/y", y), *zip(names, z)],
            config=cfg, missing_columns=set(names),
        )

    def plot3D(self, x, y, z, *, color="blue", linewidth=1.5, label=None, id=None):
        from .figure import _array, _color

        x, y, z = map(_array, (x, y, z))
        if not x.size or not x.size == y.size == z.size:
            raise ValueError("3D coordinates must be nonempty and aligned")
        sid = self._sid(id)
        s = dict(
            series_id=sid,
            label=None,
            x_column=sid + "/x",
            y_column=sid + "/y",
            z_column=sid + "/z",
            render_type={
                "Line": dict(
                    line=dict(
                        line_color=_color(color),
                        line_width=float(linewidth) * self.figure.dpi / 72,
                        line_style="Solid",
                        interpolation="Linear",
                    )
                )
            },
        )
        if label is not None:
            from .figure import _segments

            s["label"] = copy.deepcopy(
                self._config(self.figure.get_settings())["legend"]["content"]
            )
            s["label"]["segments"] = _segments(label)
        return self._install_series(
            [s],
            [(sid + "/x", x), (sid + "/y", y), (sid + "/z", z)],
            config=self._projection_config("3d"),
        )

    def scatter3D(
        self,
        x,
        y,
        z,
        *,
        color=None,
        s=20,
        c=None,
        cmap="viridis",
        vmin=None,
        vmax=None,
        marker="o",
        label=None,
        id=None,
    ):
        return self.scatter(
            x,
            y,
            z,
            s=s,
            color=color,
            c=c,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            marker=marker,
            label=label,
            id=id,
        )

    def quiver3D(self, x, y, z, u, v, w, *, color="black", scale=1.0, id=None):
        from .figure import _array, _color

        arrays = list(map(_array, (x, y, z, u, v, w)))
        if not arrays[0].size or len({a.size for a in arrays}) != 1:
            raise ValueError("3D arrow coordinates/components must be aligned")
        sid = self._sid(id)
        spec = dict(
            series_id=sid,
            label=None,
            x_column=sid + "/x",
            y_column=sid + "/y",
            z_column=sid + "/z",
            render_type={
                "Vector": dict(
                    components={
                        "Points": dict(u=sid + "/u", v=sid + "/v", w=sid + "/w")
                    },
                    style=dict(
                        color=_color(color),
                        width_px=1.0,
                        scale={"Data": dict(factor=float(scale))},
                        pivot="Tail",
                        head_length_px=6.0,
                        head_width_px=4.0,
                        min_length_px=0.0,
                    ),
                )
            },
        )
        return self._install_series(
            [spec],
            [
                (sid + "/" + k, a)
                for k, a in zip(("x", "y", "z", "u", "v", "w"), arrays)
            ],
            config=self._projection_config("3d"),
        )

    def sunburst(
        self,
        nodes,
        parents=None,
        values=None,
        *,
        colors=None,
        inner_radius=0.0,
        **properties,
    ):
        """Draw a hierarchy from nested nodes or parallel labels/parents/values."""
        from .figure import _color, _COLORS

        if parents is not None:
            labels = list(nodes)
            parents = list(parents)
            values = list(values) if values is not None else [1.0] * len(labels)
            if not len(labels) == len(parents) == len(values) or len(
                set(labels)
            ) != len(labels):
                raise ValueError(
                    "labels must be unique and aligned with parents/values"
                )
            lookup = {
                label: dict(label=str(label), value=float(value), children=[])
                for label, value in zip(labels, values)
            }
            roots = []
            for label, parent in zip(labels, parents):
                if parent in ("", None):
                    roots.append(lookup[label])
                elif parent not in lookup:
                    raise ValueError("parent is not a label")
                else:
                    lookup[parent]["children"].append(lookup[label])
            visited = set()

            def visit(label):
                if label in visited:
                    raise ValueError("sunburst hierarchy contains a cycle")
                visited.add(label)
                for child in lookup[label]["children"]:
                    visit(child["label"])

            for node in roots:
                visit(node["label"])
            if len(visited) != len(labels):
                raise ValueError("sunburst hierarchy contains a cycle or has no root")
            nodes = roots
        else:
            nodes = list(nodes)
        if not nodes:
            raise ValueError("sunburst needs a root")
        counter = [0]
        palette = list(colors) if colors is not None else _COLORS
        if not palette:
            raise ValueError("colors must not be empty")

        def convert(node):
            if not isinstance(node, dict):
                raise ValueError("nodes must be dictionaries with label/value/children")
            children = [convert(child) for child in node.get("children", [])]
            value = float(node.get("value", sum(c["value"] for c in children)))
            if not math.isfinite(value) or value < 0:
                raise ValueError("node values must be finite and nonnegative")
            if sum(c["value"] for c in children) > value + max(value, 1.0) * 1e-12:
                raise ValueError("children must sum to at most their parent value")
            i = counter[0]
            counter[0] += 1
            color = node.get("color", palette[i % len(palette)])
            return dict(
                label=str(node.get("label", "")),
                value=value,
                color=_color(color),
                explode=float(node.get("explode", 0.0)),
                children=children,
            )

        roots = [convert(node) for node in nodes]
        artist = self.pie(
            [n["value"] for n in roots],
            labels=[n["label"] for n in roots],
            colors=[tuple(n["color"][c] for c in "rgba") for n in roots],
            **properties,
        )
        state = self.figure.get_settings()
        state["radial"]["slices"] = roots
        if inner_radius:
            state["radial"]["kind"] = {"Donut": {"inner_radius": float(inner_radius)}}
        self.figure.apply_settings(state)
        return artist

    def set_axis_unit(self, axis, scale=1.0, offset=0.0):
        if axis not in ("x", "y"):
            raise ValueError("axis must be x or y")
        state = self.figure.get_settings()
        cfg = self._config(state)
        for key in (("bottom_x", "top_x") if axis == "x" else ("left_y", "right_y")):
            cfg[key]["unit"] = dict(scale=float(scale), offset=float(offset))
        self.figure.apply_settings(state)
        return self

    def set_axis_breaks(self, axis, intervals, *, gap=8.0):
        if axis not in ("x", "y"):
            raise ValueError("axis must be x or y")
        state = self.figure.get_settings()
        cfg = self._config(state)
        self._axis_node(state, axis)["breaks"] = dict(
            ranges=[{"from": float(a), "to": float(b)} for a, b in intervals],
            gap_px=float(gap),
        )
        self.figure.apply_settings(state)
        return self

    def set_probability_scale(self, axis="y", distribution="normal"):
        if axis not in ("x", "y"):
            raise ValueError("axis must be x or y")
        kind = {
            "normal": "Normal",
            "weibull": "Weibull",
            "logit": "Logistic",
            "logistic": "Logistic",
        }.get(distribution)
        if kind is None:
            raise ValueError("distribution must be normal, weibull or logistic")
        state = self.figure.get_settings()
        cfg = self._config(state)
        for key in (("bottom_x", "top_x") if axis == "x" else ("left_y", "right_y")):
            cfg[key].update(scale={"Probability": kind}, min=0.001, max=0.999)
        self.figure.apply_settings(state)
        return self

    def twiny(self, *, id=None):
        state = self.figure.get_settings()
        cfg = self._config(state)
        if cfg.get("polar") is not None:
            raise ValueError("independent X overlays need Cartesian coordinates")
        index = _document.panel_index(state, self.subplot_id)
        ids = state["identity"]["panels"][index]["overlays"]
        oid = _document.identifier(id or f"{self.subplot_id}/x{len(ids)+2}")
        x_axis = copy.deepcopy(cfg["bottom_x"])
        x_axis["line_visible"] = True
        x_axis["label_style"]["visible"] = True
        y_axis = copy.deepcopy(cfg["left_y"])
        cfg.setdefault("overlays", []).append(
            dict(x_axis=x_axis, y_axis=y_axis, link_x=False, link_y=True, series=[])
        )
        ids.append(oid)
        self.figure.apply_settings(state)
        return self.figure._axes_for(self.subplot_id, oid)

    def set_zlim(self, bottom, top):
        cfg = copy.deepcopy(self._config(self.figure.get_settings()))
        if cfg.get("view_3d") is None:
            raise ValueError("z limits require a 3D projection")
        low, high = float(bottom), float(top)
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError("limits must increase and be finite")
        cfg["right_y"].update(min=low, max=high, major_spacing=(high - low) / 5)
        self.configure(**cfg)
        return low, high

    def set_zlabel(self, text, **kwargs):
        if text:
            kwargs.setdefault("visible", True)
        return self.figure.update("axis_title_right", _axes=self, text=text, **kwargs)

    def _axis_node(self, state, axis):
        cfg = self._config(state)
        if self.overlay_id:
            o = self._overlay(state)
            if axis == "x" and not o.get("link_x", True):
                return o["x_axis"]
            if axis == "y" and not o.get("link_y", False):
                return o["y_axis"]
        return cfg["bottom_x" if axis == "x" else "left_y"]


# Preserve the same execution-local style and explicit-argument handling as the
# existing plotting constructors when this mixin takes precedence in Axes.
for _method_name in (
    "stem",
    "streamlines",
    "streamplot",
    "range_bars",
    "broken_barh",
    "waterfall",
    "candlestick",
    "ternary",
    "parallel_coordinates",
    "tripcolor",
    "tricontour",
    "tricontourf",
    "plot_trisurf",
    "energy_levels",
    "feynman",
    "bar",
    "radar",
    "rose",
    "violinplot",
    "raincloud",
    "imshow_rgb",
    "hexbin",
    "plot_surface",
    "plot3D",
    "scatter3D",
    "quiver3D",
    "sunburst",
):
    setattr(
        AdvancedMethods,
        _method_name,
        _style_runtime.styled(getattr(AdvancedMethods, _method_name)),
    )
