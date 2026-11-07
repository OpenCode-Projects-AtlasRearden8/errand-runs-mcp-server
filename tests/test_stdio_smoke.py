"""Stdio smoke test: boot the real server as a subprocess and talk MCP to it.

Uses the official `mcp` client against a throwaway data file. Skipped
cleanly if the client pieces are unavailable in the installed SDK version.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.client")

from mcp.client import Client, stdio


@pytest.fixture
def params(tmp_path: Path) -> tuple[stdio.StdioServerParameters, Path]:
    errands_path = tmp_path / "smoke.json"
    run_params = stdio.StdioServerParameters(
        command=sys.executable,
        args=["-m", "errand_runs.server"],
        env={
            **os.environ,
            "ERRANDS_PATH": str(errands_path),
            "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"),
        },
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    return run_params, errands_path


def test_stdio_roundtrip(params) -> None:
    run_params, errands_path = params

    async def main() -> str:
        async with Client(run_params) as client:
            tools_result = await client.list_tools()
            tools = (
                tools_result.tools if hasattr(tools_result, "tools") else tools_result
            )
            names = {
                t["name"] if isinstance(t, dict) else t.name for t in tools
            }
            assert {
                "log_item",
                "tally",
                "plan_run",
                "mark_bought",
                "receipt",
                "list_items",
            } <= names
            first = await client.call_tool(
                "log_item",
                {"item": "Smoke Test Cereal", "stores": ["Test Market"]},
            )
            tally_text = await client.call_tool("tally", {})
            run_text = await client.call_tool("plan_run", {})
            closed = await client.call_tool(
                "mark_bought", {"item": "Smoke Test Cereal", "price": 3.5}
            )
            receipt_text = await client.call_tool("receipt", {})
        return "\n".join(
            text.content[0].text  # type: ignore[index,union-attr]
            for text in (first, tally_text, run_text, closed, receipt_text)
        )

    text = asyncio.run(main())
    assert "Logged I-1: Smoke Test Cereal x1" in text
    assert "Test Market (1 items)" in text
    assert "up to 2 stops" in text
    assert "Closed I-1" in text
    assert "$3.50" in text
    saved = errands_path.read_text(encoding="utf-8").splitlines()
    assert len(saved) >= 2  # pretty-printed JSON of the store
