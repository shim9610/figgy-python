"""Speak the actual MCP stdio protocol, including discovery and file export."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import pytest
from figgyplot import text_segments


def test_stdio_chart_edit_layout_and_export(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def scenario():
        env = dict(
            os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "python")
        )
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "figgyplot.mcp"], env=env
        )
        with tempfile.TemporaryFile(mode="w+") as stderr:
            await check(params, stderr)

    async def check(params, stderr):
        async with stdio_client(params, errlog=stderr) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                listing = await client.list_tools()
                assert {
                    "capabilities",
                    "figure_create",
                    "chart_add",
                    "figure_theme",
                    "figure_layout",
                    "figure_export",
                    "figure_close",
                } <= {t.name for t in listing.tools}

                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result.content
                    return result.structuredContent or json.loads(
                        result.content[0].text
                    )

                caps = await call("capabilities", {})
                assert "sunburst" in caps["charts"] and "tricontourf" in caps["charts"]
                assert "imshow_rgb" in caps["charts"] and "uint32" in caps["dtypes"]
                id = (await call("figure_create", {}))["id"]
                await call("chart_add", {"id": id, "kind": "range_bars", "args": [[0, 1], [0, 1], [1, 2]],
                                         "options": {"id": "tasks", "orientation": "horizontal"}})
                links = await call("chart_add", {"id": id, "kind": "range_links",
                                                 "args": ["tasks", [[0, 1]]], "options": {"id": "dependencies"}})
                assert links["settings"]["series"][-1]["render_type"]["RangeLinks"]["links"] == [{"from": 0, "to": 1}]
                await call("figure_close", {"id": id})
                made = await call("figure_create", {"figsize": [4, 3], "dpi": 72})
                id = made["id"]
                await call(
                    "chart_add",
                    {
                        "id": id,
                        "kind": "stem",
                        "args": [{"dtype": "float32", "values": [1, 3, 2]}],
                    },
                )
                await call("figure_theme", {"id": id, "name": "midnight"})
                await call("figure_layout", {"id": id})
                for format in ("svg", "pdf"):
                    path = tmp_path / ("mcp." + format)
                    result = await call(
                        "figure_export", {"id": id, "path": str(path), "scale": 2.0}
                    )
                    assert result["bytes"] == path.stat().st_size
                await call("figure_close", {"id": id})
                for kind, args, options in [
                    (
                        "energy_levels",
                        [
                            [
                                dict(id="a", column="S", energy=0, label="Ground"),
                                dict(id="b", column="P", energy=3, label="Excited"),
                            ]
                        ],
                        {},
                    ),
                    (
                        "feynman",
                        [
                            [
                                dict(
                                    id="a",
                                    role="Incoming",
                                    at={"dtype": "float32", "values": [0, 0]},
                                    label="electron",
                                ),
                                dict(id="b", role="Outgoing", at=[1, 1]),
                            ],
                            [
                                dict(
                                    id="p",
                                    **{"from": "a", "to": "b"},
                                    particle="Fermion",
                                    label="p",
                                )
                            ],
                        ],
                        {"direction": "bottom-to-top"},
                    ),
                ]:
                    id = (await call("figure_create", {}))["id"]
                    result = await call(
                        "chart_add",
                        {"id": id, "kind": kind, "args": args, "options": options},
                    )
                    assert result["settings"]["series"]
                    for format in ("svg", "pdf"):
                        path = tmp_path / (kind + "." + format)
                        await call("figure_export", {"id": id, "path": str(path)})
                        assert (
                            path.read_bytes().startswith(b"%PDF-")
                            if format == "pdf"
                            else "<svg" in path.read_text()
                        )
                    await call("figure_close", {"id": id})

                id = (await call("figure_create", {}))["id"]
                mesh = {
                    "id": id,
                    "kind": "tripcolor",
                    "args": [[0, 1, 0], [0, 0, 1], [1, 2, 3]],
                }
                baseline = await call("figure_get", {"id": id})
                for indices in ([[0.9, 1.2, 2.8]], [[-1, 1, 2]], [[0, 1, 2**32]]):
                    result = await client.call_tool(
                        "chart_add",
                        dict(
                            mesh,
                            options={
                                "triangles": {"dtype": "uint32", "values": indices}
                            },
                        ),
                    )
                    assert result.isError and "whole numbers" in result.content[0].text
                assert await call("figure_get", {"id": id}) == baseline
                await call(
                    "chart_add",
                    dict(
                        mesh,
                        options={
                            "triangles": {"dtype": "uint32", "values": [[0, 1, 2]]}
                        },
                    ),
                )
                rgb = await call(
                    "chart_add",
                    {
                        "id": id,
                        "kind": "imshow_rgb",
                        "args": [
                            {"dtype": "uint8", "values": [[[255, 0, 0], [0, 255, 0]]]}
                        ],
                    },
                )
                assert "RgbImage" in rgb["settings"]["series"][-1]["render_type"]
                await call("figure_close", {"id": id})

                id = (await call("figure_create", {}))["id"]
                pie = await call(
                    "chart_add", {"id": id, "kind": "pie", "args": [[3, 2]]}
                )
                title = dict(
                    pie["settings"]["config"]["chart_title"]["text"],
                    segments=text_segments("Before patch"),
                )
                before = await call(
                    "figure_patch",
                    {
                        "id": id,
                        "config": {"chart_title": {"text": title, "visible": True}},
                    },
                )
                png = tmp_path / "radial.png"
                await call("figure_export", {"id": id, "path": str(png)})
                before_png = png.read_bytes()
                patch = {"id": id, "config": {"chart_title": {"visible": False}}}
                result = await client.call_tool(
                    "figure_patch", dict(patch, slices={"0": {"value": 4}})
                )
                assert result.isError
                assert await call("figure_get", {"id": id}) == before
                hidden = await call("figure_patch", patch)
                assert hidden["radial"]["chart_title"]["visible"] is False
                await call("figure_export", {"id": id, "path": str(png)})
                assert png.read_bytes() != before_png
                patched = await call(
                    "figure_patch", dict(patch, slices={"0": {"label": "Renamed"}})
                )
                assert patched["config"] == pie["settings"]["config"]
                assert patched["radial"]["chart_title"]["visible"] is False
                assert patched["radial"]["slices"][0]["label"] == "Renamed"
                await call("figure_close", {"id": id})

    asyncio.run(scenario())
