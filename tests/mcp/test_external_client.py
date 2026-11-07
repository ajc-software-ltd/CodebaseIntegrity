"""External MCP client acceptance tests (PLAN.md §21 M09).

A real MCP client (official SDK ``ClientSession``) connects to a spawned
``cii mcp`` stdio server and exercises every documented operation: the nine
tools and the five resources.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "index_status", "index_search", "index_file", "index_symbol",
    "index_scan", "index_rebuild", "index_validate", "index_dependencies",
    "index_statistics",
}
EXPECTED_RESOURCES = {
    "cii://project/status", "cii://project/index", "cii://project/statistics",
    "cii://project/languages", "cii://project/configuration",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.mark.integration
class TestExternalClient:
    def test_client_can_use_every_documented_operation(self, project_root: Path) -> None:
        import subprocess

        _write(project_root / "base.py", "class Base:\n    pass\n")
        _write(
            project_root / "child.py",
            "class Child(Base):\n    def render(self):\n        pass\n",
        )
        subprocess.run(
            [sys.executable, "-m", "cii", "init", "--root", str(project_root)],
            check=True,
            capture_output=True,
        )
        _run_client_session(project_root)


def _run_client_session(project_root: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cii", "mcp", "--root", str(project_root)],
        cwd=str(project_root),
    )

    async def session_flow() -> None:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert EXPECTED_TOOLS <= names, f"missing tools: {EXPECTED_TOOLS - names}"

                # index_status must work without any prior scan
                result = await session.call_tool("index_status", {})
                payload = _payload(result)
                assert "project_root" in payload

                # populate the index through the server itself
                scan = _payload(await session.call_tool("index_scan", {}))
                assert scan["status"] == "completed"

                assert _payload(
                    await session.call_tool("index_search", {"query": "render"})
                )["total"] == 1
                structure = _payload(
                    await session.call_tool("index_file", {"path": "child.py"})
                )
                assert structure["file_path"] == "child.py"
                assert _payload(
                    await session.call_tool("index_symbol", {"name": "Child"})
                )["total"] == 1
                rebuild = _payload(
                    await session.call_tool("index_rebuild", {"confirm": True})
                )
                assert rebuild["status"] == "completed"
                validate = _payload(
                    await session.call_tool("index_validate", {"full_scan": True})
                )
                assert validate["status"] in ("healthy", "warning")
                assert _payload(
                    await session.call_tool(
                        "index_dependencies",
                        {"symbol": "Child", "relationship_types": ["inherits"]},
                    )
                )["total"] == 1
                assert _payload(
                    await session.call_tool("index_statistics", {})
                )["total_files"] == 2

                # destructive op must refuse without confirmation
                refused = _payload(await session.call_tool("index_rebuild", {}))
                assert "error" in refused

                resources = await session.list_resources()
                uris = {str(item.uri) for item in resources.resources}
                assert EXPECTED_RESOURCES <= uris, f"missing: {EXPECTED_RESOURCES - uris}"
                for uri in EXPECTED_RESOURCES:
                    result = await session.read_resource(uri)
                    json.loads(result.contents[0].text)

    asyncio.run(session_flow())


def _payload(result) -> dict:  # type: ignore[no-untyped-def]
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError(f"no JSON payload in tool result: {result!r}")
