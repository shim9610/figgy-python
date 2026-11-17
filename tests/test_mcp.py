"""Speak the actual MCP stdio protocol, including discovery and file export."""

import asyncio
import json
import os
from pathlib import Path
import sys
import pytest


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
        async with stdio_client(params) as (read, write):
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
                made = await call("figure_create", {"figsize": [4, 3], "dpi": 72})
                id = made["id"]
                await call("chart_add", {"id": id, "kind": "stem", "args": [[1, 3, 2]]})
                await call("figure_theme", {"id": id, "name": "midnight"})
                await call("figure_layout", {"id": id})
                for format in ("svg", "pdf"):
                    path = tmp_path / ("mcp." + format)
                    result = await call(
                        "figure_export", {"id": id, "path": str(path), "scale": 2.0}
                    )
                    assert result["bytes"] == path.stat().st_size
                await call("figure_close", {"id": id})

    asyncio.run(scenario())
