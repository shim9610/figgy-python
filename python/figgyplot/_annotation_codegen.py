"""Public annotation recipes shared by Cartesian and bounded exporters."""


def annotation_calls(layer, axes, variable, dpi, rich_arg):
    from ._api_codegen import _color_literal as color, _points

    def points(value):
        return _points(value, dpi)

    for item in layer.get("items", []):
        kind, body = next(iter(item["kind"].items()))
        id = item["id"]
        handle = f"{variable}.annotation({id!r})"
        if kind == "Text":
            coords, point = next(iter(body["anchor"].items()))
            rich = body["text"]
            yield (
                f"{axes}.text({point['x']!r}, {point['y']!r}, {rich_arg(rich)}, coords={coords.lower()!r}, "
                f"fontsize={points(rich['font_size'])!r}, color={color(rich['color'])!r}, fontfamily={rich['font']!r}, id={id!r})"
            )
            yield f"{handle}.set_multialignment({rich.get('align', 'Left').lower()!r})"
            box = body.get("box_style")
            if box:
                yield (
                    f"{handle}.set_bbox(facecolor={color(box['fill'])!r}, edgecolor={color(box['border_color'])!r}, "
                    f"linewidth={points(box['border_width'])!r}, pad={points(box['padding'])!r})"
                )
        elif kind == "ReferenceLine":
            method = "axvline" if body["axis"] == "X" else "axhline"
            yield f"{axes}.{method}({body['value']!r}, id={id!r})"
        elif kind == "Span":
            method = "axvspan" if body["axis"] == "X" else "axhspan"
            yield f"{axes}.{method}({body['from']!r}, {body['to']!r}, color={color(body['fill'])!r}, alpha=1, id={id!r})"
        elif kind == "Arrow":
            yield f"{axes}.arrow(0, 0, 0, 0, coords='ratio', id={id!r})"
            source, start = next(iter(body["from"].items()))
            destination, end = next(iter(body["to"].items()))
            yield (
                f"{handle}.set_endpoints({(start['x'], start['y'])!r}, {(end['x'], end['y'])!r}, "
                f"coords={source.lower()!r}, endcoords={destination.lower()!r})"
            )
        else:
            raise ValueError("unknown annotation kind; use exact recovery")
        if kind in ("Arrow", "ReferenceLine"):
            line = body["style"]["line"] if kind == "Arrow" else body["style"]
            ls = dict(Solid="-", Dash="--", Dot=":", DashDot="-.")[line["style"]]
            args = f"color={color(line['color'])!r}, linewidth={points(line['width'])!r}, linestyle={ls!r}"
            if kind == "Arrow":
                args += f", head_length={points(body['style']['head_length'])!r}, head_width={points(body['style']['head_width'])!r}"
            yield f"{handle}.set_style({args})"
            rich = body.get("text" if kind == "Arrow" else "label")
            if rich:
                yield (
                    f"{handle}.set_label({rich_arg(rich)}, fontsize={points(rich['font_size'])!r}, "
                    f"color={color(rich['color'])!r}, fontfamily={rich['font']!r}, multialignment={rich.get('align', 'Left').lower()!r})"
                )
        if not item.get("visible", True):
            yield f"{handle}.set_visible(False)"
    yield f"{variable}.set_annotations_visible({layer['visible']!r})"
