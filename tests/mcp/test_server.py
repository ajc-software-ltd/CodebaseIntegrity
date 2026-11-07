"""In-process MCP server tests via MCPServer.call_tool/read_resource."""

import asyncio
import json
from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.database.database import Database
from cii.database.repositories import ProjectRepository
from cii.mcp.server import build_server


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def application(project_root: Path):
    config = CiiConfig.defaults()
    database = Database.open(project_root)
    ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    app = Application(project_root, config, database)
    _write(project_root / "base.py", "class Base:\n    pass\n")
    _write(project_root / "child.py", "class Child(Base):\n    def render(self):\n        pass\n")
    app.scan()
    yield app
    database.close()


def _payload(result) -> dict:
    """Extract the JSON payload from a CallToolResult."""
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError(f"no JSON payload in tool result: {result!r}")


def _call(mcp, name: str, arguments: dict | None = None) -> dict:
    return _payload(asyncio.run(mcp.call_tool(name, arguments or {})))


class TestServerTools:
    def test_all_documented_tools_callable(self, application) -> None:
        mcp = build_server(application)
        root = str(application.project_root)

        status = _call(mcp, "index_status")
        assert status["project_name"] == "demo"

        found = _call(mcp, "index_search", {"query": "render"})
        assert found["total"] == 1

        structure = _call(mcp, "index_file", {"path": "child.py"})
        assert structure["file_path"] == "child.py"

        symbol = _call(mcp, "index_symbol", {"name": "Child"})
        assert symbol["total"] == 1

        scan = _call(mcp, "index_scan", {})
        assert scan["status"] == "completed"

        rebuild = _call(mcp, "index_rebuild", {"confirm": True})
        assert rebuild["status"] == "completed"

        validate = _call(mcp, "index_validate", {"full_scan": True})
        assert validate["status"] in ("healthy", "warning")

        deps = _call(mcp, "index_dependencies",
                    {"symbol": "Child", "relationship_types": ["inherits"]})
        assert deps["total"] == 1

        stats = _call(mcp, "index_statistics")
        assert stats["total_files"] == 2
        assert root  # sanity

    def test_rebuild_without_confirm_returns_error(self, application) -> None:
        mcp = build_server(application)
        result = _call(mcp, "index_rebuild", {})
        assert "error" in result
        assert "confirmation" in result["error"]["message"]

    def test_path_traversal_returns_structured_error(self, application) -> None:
        mcp = build_server(application)
        result = _call(mcp, "index_file", {"path": "../outside.py"})
        assert "error" in result
        assert result["error"]["type"] == "PathSecurityError"

    def test_unregistered_project_returns_error(self, project_root: Path) -> None:
        database = Database.open(project_root)
        app = Application(project_root, CiiConfig.defaults(), database)
        try:
            mcp = build_server(app)
            result = _call(mcp, "index_status")
            assert "error" in result
        finally:
            database.close()


class TestServerResources:
    def test_resources_readable(self, application) -> None:
        mcp = build_server(application)

        def read(uri: str) -> dict:
            result = asyncio.run(mcp.read_resource(uri))
            contents = result.contents if hasattr(result, "contents") else result
            return json.loads(contents[0].content)

        status = read("cii://project/status")
        assert status["project_name"] == "demo"
        index = read("cii://project/index")
        assert len(index["files"]) == 2
        stats = read("cii://project/statistics")
        assert stats["total_files"] == 2
        languages = read("cii://project/languages")
        assert "python" in languages["supported"]
        config = read("cii://project/configuration")
        assert config["scan"]["hash_algorithm"] == "sha256"
