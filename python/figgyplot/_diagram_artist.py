"""Stable-ID diagram editing over the accepted renderer model.

Lengths are points; positions and energies remain diagram data coordinates.
No topology, scientific metadata or source arrays are inferred or cached here.
"""

import copy
import json
from .figure import Artist, _color, _segments
from ._validation import number
from ._native import series_template_json


def _pair(value, name):
    values = [number(v, name) for v in value]
    if len(values) != 2:
        raise ValueError(name + " requires two components")
    return values


def _defaults(tag):
    kind = {"EnergyLevels": "energy_levels", "Feynman": "feynman"}[tag]
    return json.loads(series_template_json(kind))["render_type"][tag]["style"]


def _set_wavelength_labels(style, settings, figure):
    from collections.abc import Mapping
    from .figure import _merge
    from ._native import wavelength_labels_json
    from ._diagram_input import plain

    if settings is None or settings is False:
        style.pop("wavelength_labels", None)
        return
    if settings is True:
        settings = {}
    if not isinstance(settings, Mapping):
        raise TypeError("wavelength_labels must be a boolean or a mapping")
    options = plain(settings)
    labels = copy.deepcopy(style.get("wavelength_labels") or json.loads(wavelength_labels_json()))
    fmt = labels.setdefault("format", {})
    if "decimals" in options:
        decimals = options.pop("decimals")
        if decimals is None:
            fmt.pop("decimals", None)
        else:
            fmt["decimals"] = decimals
    if "trim_zeros" in options:
        fmt["trim_zeros"] = options.pop("trim_zeros")
    text = labels["text"]
    if "fontsize" in options:
        text["font_size"] = number(options.pop("fontsize"), "fontsize", positive=True) * figure.dpi / 72
    if "color" in options:
        text["color"] = _color(options.pop("color"))
    if "font" in options:
        text["font"] = figure._check_font(options.pop("font"))
    unknown = options.keys() - {"unit", "text", "format"}
    if unknown:
        raise TypeError("unknown wavelength label options: " + ", ".join(sorted(unknown)))
    style["wavelength_labels"] = _merge(labels, options)


class DiagramArtist(Artist):
    """An energy-level or Feynman series; edit its rows through stable IDs."""

    def _tag(self, state):
        tag = next(iter(self._spec(state)["render_type"]))
        if tag not in ("EnergyLevels", "Feynman"):
            raise ValueError("artist no longer contains a diagram")
        return tag

    def _edit_diagram(self, operation):
        with self.figure._lock:
            state = self.figure.get_settings()
            tag = self._tag(state)
            operation(self._spec(state)["render_type"][tag], tag)
            self.figure.apply_settings(state)
        return self

    def _element(self, collection, id, tag):
        if self._tag(self.figure.get_settings()) != tag:
            raise AttributeError(collection + " do not belong to this diagram")
        return DiagramElement(self, collection, id)

    def level(self, id):
        return self._element("levels", id, "EnergyLevels")

    def transition(self, id):
        return self._element("transitions", id, "EnergyLevels")

    def limit(self, id):
        return self._element("limits", id, "EnergyLevels")

    def band(self, id):
        return self._element("bands", id, "EnergyLevels")

    def vertex(self, id):
        return self._element("vertices", id, "Feynman")

    def propagator(self, id):
        return self._element("propagators", id, "Feynman")

    def get_elements(self):
        """Return record IDs grouped by collection, without exposing mutable state."""
        state = self.figure.get_settings()
        tag = self._tag(state)
        body = self._spec(state)["render_type"][tag]
        names = (
            ("levels", "transitions", "limits", "bands")
            if tag == "EnergyLevels"
            else ("vertices", "propagators")
        )
        return {name: tuple(row["id"] for row in body.get(name, [])) for name in names}

    def get_style(self):
        state = self.figure.get_settings()
        tag = self._tag(state)
        style = copy.deepcopy(_defaults(tag))
        from .figure import _merge

        _merge(style, self._spec(state)["render_type"][tag].get("style", {}))
        part = style["level"] if tag == "EnergyLevels" else style
        return dict(
            color=tuple(part["color"][k] for k in "rgba"),
            linewidth=part["width"] * 72 / self.figure.dpi,
        )

    def set_style(self, *, color=None, linewidth=None, **properties):
        """Set common stroke style in points; advanced model fields remain explicit."""

        def edit(body, tag):
            from ._advanced import _diagram_style_update
            from .figure import _merge
            from ._diagram_input import plain

            style = copy.deepcopy(_defaults(tag))
            _merge(style, body.get("style", {}))
            remaining = plain(properties)
            if "wavelength_labels" in remaining and tag == "EnergyLevels":
                _set_wavelength_labels(style, remaining.pop("wavelength_labels"), self.figure)
            _diagram_style_update(style, remaining)
            part = style["level"] if tag == "EnergyLevels" else style
            if color is not None:
                part["color"] = _color(color)
            if linewidth is not None:
                part["width"] = (
                    number(linewidth, "linewidth", positive=True) * self.figure.dpi / 72
                )
            body["style"] = style

        return self._edit_diagram(edit)

    def set_wavelength_labels(self, visible=True, **options):
        """Format each unlabelled transition's stored wavelength, with no unit conversion."""
        if not isinstance(visible, bool):
            raise TypeError("wavelength label visibility must be boolean")
        return self.set_style(wavelength_labels=options if visible else False)

    def set_wavelength_colors(self, unit="nm", *, ultraviolet=None, infrared=None):
        """Color transition arrows by wavelength. Pass None to restore series colors."""
        from ._native import spectral_colors_json

        def edit(body, tag):
            if tag != "EnergyLevels":
                raise AttributeError("wavelength colors require an energy-level diagram")
            transition = body.setdefault("style", {}).setdefault("transition", {})
            if unit is None:
                transition.pop("color_by_wavelength", None)
                return
            try:
                wire = {
                    "nm": "Nm", "angstrom": "Angstrom", "å": "Angstrom",
                    "um": "Um", "µm": "Um", "μm": "Um",
                }[unit.strip().lower()]
            except (AttributeError, KeyError):
                raise ValueError("wavelength unit must be nm, angstrom or um") from None
            colors = copy.deepcopy(transition.get("color_by_wavelength") or json.loads(spectral_colors_json()))
            colors["unit"] = wire
            for key, value in (("ultraviolet", ultraviolet), ("infrared", infrared)):
                if value is not None:
                    colors[key] = _color(value)
            transition["color_by_wavelength"] = colors

        return self._edit_diagram(edit)

    def set(self, **properties):
        properties = {
            dict(c="color", lw="linewidth").get(k, k): v for k, v in properties.items()
        }
        with self.figure.batch_update():
            if "label" in properties:
                self.set_label(properties.pop("label"))
            if "alpha" in properties:
                self.set_alpha(properties.pop("alpha"))
            if properties:
                self.set_style(**properties)
        return self

    def reset_style(self):
        return self._edit_diagram(lambda body, tag: body.pop("style", None))

    def set_color(self, value):
        return self.set_style(color=value)

    def get_color(self):
        return self.get_style()["color"]

    def set_linewidth(self, value):
        return self.set_style(linewidth=value)

    def get_linewidth(self):
        return self.get_style()["linewidth"]

    def set_alpha(self, value):
        alpha = number(value, "alpha")
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be in 0..1")

        def edit(body, tag):
            from .figure import _merge

            style = copy.deepcopy(_defaults(tag))
            _merge(style, body.get("style", {}))

            def opacity(node):
                if isinstance(node, dict):
                    if set(node) == set("rgba"):
                        node["a"] = alpha
                    else:
                        for child in node.values():
                            opacity(child)

            opacity(style)
            body["style"] = style
            for row in body.get("propagators", []):
                opacity(row.get("color"))
            for row in body.get("vertices", []):
                opacity(row.get("marker"))

        return self._edit_diagram(edit)

    def set_layout(self, *, direction):
        from ._diagram_input import enum_name

        def edit(body, tag):
            if tag != "Feynman":
                raise AttributeError("layout direction requires a Feynman diagram")
            body.setdefault("layout", {})["direction"] = enum_name(
                direction, ("LeftToRight", "BottomToTop")
            )

        return self._edit_diagram(edit)

    def set_view(self, view):
        from ._diagram_input import enum_name

        def edit(body, tag):
            if tag != "EnergyLevels":
                raise AttributeError("level view requires an energy-level diagram")
            body["show"] = enum_name(view, ("Main", "Components"))

        return self._edit_diagram(edit)


class DiagramElement:
    """One row, looked up by ID on each edit so reordering cannot retarget it."""

    def __init__(self, artist, collection, id):
        self.artist, self.collection, self.id = artist, collection, id
        self._row(artist._body(artist.figure.get_settings()))

    def _row(self, body):
        row = next(
            (row for row in body.get(self.collection, []) if row["id"] == self.id), None
        )
        if row is None:
            raise ValueError("unknown " + self.collection + " ID: " + str(self.id))
        return row

    def _edit(self, operation):
        self.artist._edit_diagram(
            lambda body, tag: operation(self._row(body), body, tag)
        )
        return self

    def get(self):
        return copy.deepcopy(
            self._row(self.artist._body(self.artist.figure.get_settings()))
        )

    def set_label(self, text, *, fontsize=None, color=None, fontfamily=None):
        def edit(row, body, tag):
            if text is None:
                if any(v is not None for v in (fontsize, color, fontfamily)):
                    raise ValueError("a cleared label has no typography")
                row.pop("label", None)
                return
            rich = copy.deepcopy(
                row.get("label")
                or self.artist._panel_axes(self.artist.figure.get_settings())._config(
                    self.artist.figure.get_settings()
                )["legend"]["content"]
            )
            rich["segments"] = _segments(text, dpi=self.artist.figure.dpi)
            if fontsize is not None:
                rich["font_size"] = (
                    number(fontsize, "fontsize", positive=True)
                    * self.artist.figure.dpi
                    / 72
                )
            if color is not None:
                rich["color"] = _color(color)
            if fontfamily is not None:
                rich["font"] = self.artist.figure._check_font(fontfamily)
            row["label"] = rich

        return self._edit(edit)

    def set_label_style(self, *, fontsize=None, color=None, fontfamily=None):
        current = self.get().get("label")
        if current is None:
            raise ValueError("set a label before editing its typography")
        return self.set_label(
            current["segments"], fontsize=fontsize, color=color, fontfamily=fontfamily
        )

    def get_label(self):
        from .figure import _text

        label = self.get().get("label")
        return "" if label is None else _text(label)

    def set_role(self, role):
        if self.collection != "vertices":
            raise AttributeError("role requires a Feynman vertex")
        from ._diagram_input import enum_name

        value = enum_name(role, ("Incoming", "Outgoing", "Internal"))
        return self._edit(lambda row, body, tag: row.update(role=value))

    def set_marker(self, marker=None, *, radius=None, facecolor=None):
        if self.collection != "vertices":
            raise AttributeError("marker requires a Feynman vertex")
        from ._diagram_input import enum_name

        value = (
            None
            if marker is None
            else enum_name(marker, ("Hidden", "Dot", "Cross", "CircledCross", "Blob"))
        )
        if value == "Blob":
            if radius is None:
                raise ValueError("a blob marker requires radius in points")
            value = {
                "Blob": dict(
                    radius_px=number(radius, "radius", positive=True)
                    * self.artist.figure.dpi
                    / 72,
                    fill=None if facecolor is None else _color(facecolor),
                )
            }
        elif radius is not None or facecolor is not None:
            raise ValueError("radius and facecolor require a blob marker")
        return self._edit(lambda row, body, tag: row.update(marker=value))

    def set_offset(self, fraction):
        if self.collection != "transitions":
            raise AttributeError("slot offset requires an energy transition")
        value = number(fraction, "transition offset")
        return self._edit(lambda row, body, tag: row.update(x_offset=value))

    def set_label_offset(self, offset):
        value = [v * self.artist.figure.dpi / 72 for v in _pair(offset, "label offset")]
        return self._edit(lambda row, body, tag: row.update(label_offset=value))

    def get_label_offset(self):
        return tuple(
            v * 72 / self.artist.figure.dpi
            for v in self.get().get("label_offset", [0, 0])
        )

    def set_energy(self, energy):
        if self.collection not in ("levels", "limits"):
            raise AttributeError("energy requires a level or limit")
        value = number(energy, "energy")
        return self._edit(lambda row, body, tag: row.update(energy=value))

    def set_position(self, position):
        if self.collection != "vertices":
            raise AttributeError("position requires a Feynman vertex")
        value = None if position is None else _pair(position, "vertex position")

        def edit(row, body, tag):
            if value is None:
                row.pop("at", None)
            else:
                row["at"] = value

        return self._edit(edit)

    def get_position(self):
        """Return the explicit position, or None for renderer automatic placement."""
        return copy.deepcopy(self.get().get("at"))

    def set_bend(self, degrees=None):
        if self.collection != "propagators":
            raise AttributeError("bend requires a propagator")
        value = None if degrees is None else number(degrees, "bend")
        return self._edit(lambda row, body, tag: row.update(bend=value))

    def set_particle(self, particle):
        if self.collection != "propagators":
            raise AttributeError("particle requires a propagator")
        from ._diagram_input import enum_name, PARTICLES

        value = enum_name(particle, PARTICLES)
        return self._edit(lambda row, body, tag: row.update(particle=value))

    def set_momentum(
        self, label=None, *, side="left", reversed=False, label_offset=(0, 0)
    ):
        """Set or clear a propagator's momentum arrow; offsets use points."""
        if self.collection != "propagators":
            raise AttributeError("momentum requires a Feynman propagator")
        if not isinstance(reversed, bool):
            raise TypeError("reversed must be a boolean")
        from ._diagram_input import enum_name

        side = enum_name(side, ("Left", "Right"))
        offset = [
            v * self.artist.figure.dpi / 72
            for v in _pair(label_offset, "momentum label offset")
        ]

        def edit(row, body, tag):
            if label is None:
                row.pop("momentum", None)
                return
            rich = copy.deepcopy(
                self.artist._panel_axes(self.artist.figure.get_settings())._config(
                    self.artist.figure.get_settings()
                )["legend"]["content"]
            )
            rich["segments"] = _segments(label, dpi=self.artist.figure.dpi)
            row["momentum"] = dict(
                label=rich, side=side, reversed=reversed, label_offset=offset
            )

        return self._edit(edit)

    def set_endpoints(self, source, target):
        if self.collection not in ("propagators", "transitions"):
            raise AttributeError("endpoints require a transition or propagator")

        def edit(row, body, tag):
            names = {
                r["id"] for r in body["vertices" if tag == "Feynman" else "levels"]
            }
            if source not in names or target not in names:
                raise ValueError("endpoints must name existing record IDs")
            row.update(
                dict(
                    zip(
                        ("from", "to") if tag == "Feynman" else ("lower", "upper"),
                        (source, target),
                    )
                )
            )

        return self._edit(edit)

    def set_style(self, *, color=..., linewidth=...):
        if self.collection not in ("propagators", "transitions"):
            raise AttributeError("stroke overrides require a transition or propagator")
        if self.collection == "transitions" and linewidth is not ...:
            raise AttributeError("transition widths belong to diagram.set_style()")

        def edit(row, body, tag):
            if color is not ...:
                row["color"] = None if color is None else _color(color)
            if linewidth is not ...:
                row["width_px"] = (
                    None
                    if linewidth is None
                    else number(linewidth, "linewidth", positive=True)
                    * self.artist.figure.dpi
                    / 72
                )

        return self._edit(edit)

    def set_color(self, color):
        return self.set_style(color=color)

    def set_linewidth(self, linewidth):
        return self.set_style(linewidth=linewidth)

    def reset_style(self):
        return self.set_color(None) if self.collection == "transitions" else self.set_style(color=None, linewidth=None)

    def select(self, *, label=False):
        with self.artist.figure._lock:
            state = self.artist.figure.get_settings()
            body = self.artist._body(state)
            row = self._row(body)
            index = body[self.collection].index(row)
            tag = self.artist._tag(state)
            part = {
                "levels": "level",
                "transitions": "transition",
                "limits": "limit",
                "bands": "band",
                "vertices": "vertex",
                "propagators": "propagator",
            }[self.collection]
            if tag == "EnergyLevels":
                if label or self.collection in ("limits", "bands"):
                    ref = dict(kind="value_label", category_index=index, part=part)
                else:
                    ref = (
                        dict(kind="histogram_bin", bin_index=index)
                        if self.collection == "levels"
                        else dict(kind="point", point_index=index)
                    )
            elif label:
                ref = dict(kind="feynman_label", index=index, part=part)
            else:
                ref = (
                    dict(kind="feynman_vertex", vertex_index=index)
                    if self.collection == "vertices"
                    else dict(kind="feynman_propagator", propagator_index=index)
                )
            ref["series_id"] = self.artist.id
            state["config"]["picked_data"] = dict(refs=[ref])
            self.artist.figure.apply_settings(state)
        return self
