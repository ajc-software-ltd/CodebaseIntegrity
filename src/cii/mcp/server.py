"""CII MCP server (PLAN.md §12).

Built on the official Python MCP SDK (v2 ``MCPServer``), stdio transport.
The server is a thin wrapper over :mod:`cii.mcp.tools` and
:mod:`cii.mcp.resources`: no business logic lives here.

Error handling: CII errors are returned to the caller as structured
``{"error": {...}}`` payloads instead of crashing the session; unexpected
errors are logged with their traceback and returned as ``internal`` errors.
The index is read-only for callers except the explicitly confirmed
``index_rebuild`` (PLAN.md §12.3).
"""

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from cii import __version__
from cii.application import Application
from cii.core.exceptions import CiiError
from cii.database.database import DATABASE_FILE_NAME
from cii.mcp import resources as resource_impl
from cii.mcp import tools as tool_impl

_logger = logging.getLogger("cii.mcp")

_INSTRUCTIONS = (
    "Codebase Integrity & Intelligence (CII): a persistent structural index "
    "of the project. Use index_search/index_symbol before creating new "
    "classes or functions to discover existing implementations; use "
    "index_file to see a file's structure; index_scan refreshes the index; "
    "index_validate reports integrity. The index identifies what exists — "
    "retrieve the actual source before modifying existing functionality."
)


def _guard(app: Application | None, project_root: Path, call) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run a tool body under the database lock, converting failures into
    structured error payloads."""
    if app is None:
        return {"error": {
            "type": "ProjectRootError",
            "message": (
                f"CII is not initialised in {project_root} (run 'cii init' there)"
            ),
        }}
    try:
        with app.database.locked():
            result = call()
        return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    except CiiError as error:
        return {"error": {"type": type(error).__name__, "message": str(error)}}
    except Exception as error:  # noqa: BLE001 — surfaced, never swallowed silently
        _logger.exception("unexpected MCP tool failure")
        return {"error": {"type": "internal", "message": f"{type(error).__name__}: {error}"}}


def _read_resource(app: Application | None, project_root: Path, call) -> str:  # type: ignore[no-untyped-def]
    """Run a resource body under the database lock (failures propagate to MCP)."""
    if app is None:
        return json.dumps({"error": {
            "type": "ProjectRootError",
            "message": (
                f"CII is not initialised in {project_root} (run 'cii init' there)"
            ),
        }})
    with app.database.locked():
        return call()


def build_server(
    app: Application | None, project_root: Path | None = None
) -> MCPServer:
    """Assemble the CII MCP server around an open application.

    ``app`` is None for uninitialised projects: every tool then returns a
    structured "run cii init" error instead of failing the session.
    """
    root = project_root or (app.project_root if app is not None else Path.cwd())
    mcp = MCPServer(
        name="cii",
        version=__version__,
        description="Codebase Integrity & Intelligence — structural project index.",
        instructions=_INSTRUCTIONS,
    )

    @mcp.tool(name="index_status",
              description="Current health and status of the project index.")
    def index_status() -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_status(app))

    @mcp.tool(name="index_search",
              description="Search indexed symbols by name (filters: symbol_type, "
                          "language; paginated via limit/offset; expanded adds "
                          "signatures and line numbers).")
    def index_search(
        query: str,
        symbol_type: str | None = None,
        language: str | None = None,
        limit: int = 20,
        offset: int = 0,
        expanded: bool = False,
    ) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_search(
            app, query,
            symbol_type=symbol_type, language=language,
            limit=limit, offset=offset, expanded=expanded,
        ))

    @mcp.tool(name="index_file",
              description="Return the structural index of one project file.")
    def index_file(path: str) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_file(app, path))

    @mcp.tool(name="index_symbol",
              description="Locate a specific symbol (by name) and its structural "
                          "metadata; optionally restrict to one file.")
    def index_symbol(name: str, file: str | None = None) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_symbol(app, name, file=file))

    @mcp.tool(name="index_scan",
              description="Run an incremental index scan (synchronous) and return "
                          "the scan identifier and operation status.")
    def index_scan(path: str | None = None) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_scan(app, path=path))

    @mcp.tool(name="index_rebuild",
              description="Complete index rebuild. Destructive maintenance: "
                          "requires confirm=true; the previous database is "
                          "backed up and preserved until the rebuild succeeds.")
    def index_rebuild(confirm: bool = False) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_rebuild(app, confirm=confirm))

    @mcp.tool(name="index_validate",
              description="Run integrity validation (read-only); full_scan=true "
                          "also re-parses files and compares symbols.")
    def index_validate(full_scan: bool = False) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_validate(app, full_scan=full_scan))

    @mcp.tool(name="index_dependencies",
              description="Known structural relationships for a symbol "
                          "(contains/inherits/implements; evidence-backed only).")
    def index_dependencies(
        symbol: str, relationship_types: list[str] | None = None
    ) -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_dependencies(
            app, symbol, relationship_types=relationship_types
        ))

    @mcp.tool(name="index_statistics",
              description="Project-level structural statistics and recent scan "
                          "performance.")
    def index_statistics() -> dict[str, Any]:
        return _guard(app, root, lambda: tool_impl.index_statistics(app))

    @mcp.resource("cii://project/status", name="project_status",
                  mime_type="application/json")
    def project_status() -> str:
        return _read_resource(app, root, lambda: resource_impl.status_resource(app))

    @mcp.resource("cii://project/index", name="project_index",
                  mime_type="application/json")
    def project_index() -> str:
        return _read_resource(app, root, lambda: resource_impl.index_resource(app))

    @mcp.resource("cii://project/statistics", name="project_statistics",
                  mime_type="application/json")
    def project_statistics() -> str:
        return _read_resource(app, root, lambda: resource_impl.statistics_resource(app))

    @mcp.resource("cii://project/languages", name="project_languages",
                  mime_type="application/json")
    def project_languages() -> str:
        return _read_resource(app, root, lambda: resource_impl.languages_resource(app))

    @mcp.resource("cii://project/configuration", name="project_configuration",
                  mime_type="application/json")
    def project_configuration() -> str:
        return _read_resource(app, root, lambda: resource_impl.configuration_resource(app))

    return mcp


def serve(project_root: Path) -> None:
    """Run the CII MCP server on stdio for one project root.

    When the project is not initialised (no ``.cii`` database), the server
    still starts — every tool returns a structured "run cii init" error, so a
    single global registration is safe in directories without CII.
    """
    from cii.utilities.paths import cii_data_dir

    initialised = (cii_data_dir(project_root) / DATABASE_FILE_NAME).is_file()
    app = Application.open(project_root, configure_logging=True) if initialised else None
    try:
        mcp = build_server(app, project_root=project_root)
        mcp.run(transport="stdio")
    finally:
        if app is not None:
            app.close()
