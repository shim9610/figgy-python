"""Adapt renderer CSS-pixel pages to the Figure's physical inch size."""

from io import BytesIO
import math
import re


def physical_size(data, format, dpi):
    dpi = float(dpi)
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError("dpi must be positive and finite")
    if format == "png" or dpi == 96:
        return bytes(data)
    factor = 96 / dpi
    if format == "svg":
        text = bytes(data).decode("utf-8")
        match = re.search(r"<svg\b[^>]*>", text)
        if match is None:
            raise ValueError("renderer returned no SVG root")
        root = re.sub(
            r'\b(width|height)="([0-9.eE+-]+)pt"',
            lambda m: f'{m[1]}="{float(m[2])*factor:.12g}pt"',
            match[0],
        )
        return (text[: match.start()] + root + text[match.end() :]).encode("utf-8")
    if format == "pdf":
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(BytesIO(data))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page).scale_by(factor)
        if reader.metadata:
            writer.add_metadata(
                {str(k): str(v) for k, v in reader.metadata.items() if v is not None}
            )
        stream = BytesIO()
        writer.write(stream)
        return stream.getvalue()
    raise ValueError("format must be png, svg or pdf")
