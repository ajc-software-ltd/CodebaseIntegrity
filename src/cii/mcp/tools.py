"""MCP tool implementations (PLAN.md §12.1, §12.3).

Plain functions over an :class:`Application` — the MCP server is a thin
wrapper, so every operation is testable in-process. Security rules enforced
here:

- all path arguments are validated and must resolve inside the project root
  (traversal is rejected);
- the index is read-only to callers except scan/rebuild, which only ever
  touch CII's own database and generated output — never source files;
- destructive maintenance (``index_rebuild``) requires explicit confirmation.
"""

from pathlib import Path

from cii.application import Application
from cii.core.exceptions import CiiError
from cii.database.repositories import (
    FileRepository,
    IntegrityReportRepository,
    ProjectRepository,
    ScanHistoryRepository,
    SymbolRepository,
)
from cii.integrity.validator import Validator
from cii.mcp.schemas import (
    IndexDependenciesTool,
    IndexRebuildTool,
    IndexScanTool,
    IndexSearchTool,
    IndexStatisticsTool,
    IndexStatusTool,
    IndexSymbolTool,
    IndexValidateTool,
    ScanHistoryEntry,
)
from cii.search.relationship_search import search_relationships
from cii.search.symbol_search import file_structure, search_symbols
from cii.utilities.paths import require_within_root, validate_relative_path


def _project_id(app: Application) -> str:
    project = ProjectRepository(app.database.connection).get_by_root(
        str(app.project_root)
    )
    if project is None:
        raise CiiError(f"project not registered in CII: {app.project_root} (run 'cii init')")
    return project.project_id


def _resolve_user_path(app: Application, path: str) -> tuple[Path, str]:
    """Validate a caller-supplied path and return (absolute, relative)."""
    candidate = Path(path)
    if candidate.is_absolute():
        absolute = require_within_root(candidate, app.project_root)
    else:
        relative = validate_relative_path(path)
        absolute = require_within_root(app.project_root / relative, app.project_root)
    return absolute, absolute.relative_to(app.project_root).as_posix()


def index_status(app: Application) -> IndexStatusTool:
    project_id = _project_id(app)
    project = ProjectRepository(app.database.connection).get_by_root(
        str(app.project_root)
    )
    files = FileRepository(app.database.connection).list_all(project_id)
    by_status: dict[str, int] = {}
    for file_row in files:
        by_status[file_row.scan_status] = by_status.get(file_row.scan_status, 0) + 1
    pending = by_status.get("pending", 0)
    failed = by_status.get("failed", 0)
    if failed or pending:
        health = "incomplete"
    else:
        health = "healthy"
    latest = IntegrityReportRepository(app.database.connection).list_recent(project_id, 1)
    return IndexStatusTool(
        project_name=project.project_name,
        project_root=project.project_root,
        index_version=project.index_version,
        indexed_file_count=len(files),
        indexed_symbol_count=SymbolRepository(app.database.connection)
        .count_for_project(project_id),
        last_successful_scan=project.last_scan,
        pending_files=pending,
        failed_files=failed,
        files_by_status=by_status,
        health=health,
        last_validation_status=latest[0].report_status if latest else None,
    )


def index_search(
    app: Application,
    query: str,
    symbol_type: str | None = None,
    language: str | None = None,
    limit: int = 20,
    offset: int = 0,
    expanded: bool = False,
) -> IndexSearchTool:
    page = search_symbols(
        app.database,
        _project_id(app),
        query,
        symbol_type=symbol_type,
        language=language,
        limit=limit,
        offset=offset,
        expanded=expanded,
    )
    return IndexSearchTool(**page.model_dump())


def index_file(app: Application, path: str):
    """Structural index of one file (schema: FileStructure)."""
    _absolute, relative = _resolve_user_path(app, path)
    structure = file_structure(app.database, _project_id(app), relative)
    if structure is None:
        raise CiiError(f"file not indexed: {relative}")
    return structure


def index_symbol(app: Application, name: str, file: str | None = None) -> IndexSymbolTool:
    _absolute, relative = (None, None)
    if file is not None:
        _absolute, relative = _resolve_user_path(app, file)
    page = search_symbols(
        app.database, _project_id(app), name, limit=100, expanded=True
    )
    hits = [
        hit for hit in page.results
        if hit.name == name or hit.fully_qualified_name == name
    ]
    if relative is not None:
        hits = [hit for hit in hits if hit.file_path == relative]
    return IndexSymbolTool(query=name, total=len(hits), results=hits)


def index_scan(app: Application, path: str | None = None) -> IndexScanTool:
    """Run an incremental scan synchronously and return its identifier.

    When ``path`` is supplied it is validated against the project root and
    included in the scan scope (the scan covers all detected changes).
    """
    scanned_path = None
    if path is not None:
        _absolute, scanned_path = _resolve_user_path(app, path)
    outcome = app.scan()
    changes = outcome.scan.changes
    return IndexScanTool(
        scan_id=outcome.scan.scan_id,
        status="completed",
        mode="full" if outcome.scan.full else "incremental",
        path=scanned_path,
        added=len(changes.added),
        modified=len(changes.modified),
        deleted=len(changes.deleted),
        renamed=len(changes.renamed),
        unchanged=changes.unchanged_count,
        files_indexed=outcome.index.files_indexed,
        files_failed=outcome.index.files_failed,
        symbols_added=outcome.index.symbols_added,
        symbols_updated=outcome.index.symbols_updated,
        symbols_removed=outcome.index.symbols_removed,
    )


def index_rebuild(app: Application, confirm: bool = False) -> IndexRebuildTool:
    """Complete index rebuild. Requires ``confirm: true`` (destructive)."""
    if not confirm:
        raise CiiError(
            "index_rebuild replaces the project's index state and requires "
            "explicit confirmation: pass confirm=true"
        )
    outcome = app.rebuild()
    return IndexRebuildTool(
        status="completed",
        scan_id=outcome.scan.scan_id,
        backup_path=outcome.backup_path,
        files_indexed=outcome.index.files_indexed,
        symbols_indexed=sum(o.symbols_indexed for o in outcome.index.outcomes),
    )


def index_validate(app: Application, full_scan: bool = False) -> IndexValidateTool:
    summary = Validator(app.project_root, app.config, app.database).validate(
        full_scan=full_scan
    )
    return IndexValidateTool(
        status=summary.status.value,
        errors=summary.errors,
        warnings=summary.warnings,
        files_checked=summary.files_checked,
        full_scan=summary.full_scan,
        findings=[finding.model_dump(mode="json") for finding in summary.findings],
    )


def index_dependencies(
    app: Application, symbol: str, relationship_types: list[str] | None = None
) -> IndexDependenciesTool:
    page = search_relationships(
        app.database,
        _project_id(app),
        symbol,
        relationship_types=relationship_types,
    )
    return IndexDependenciesTool(symbol=symbol, total=page.total, results=page.results)


def index_statistics(app: Application) -> IndexStatisticsTool:
    project_id = _project_id(app)
    connection = app.database.connection
    files = FileRepository(connection).list_all(project_id)
    by_language: dict[str, int] = {}
    for file_row in files:
        by_language[file_row.language] = by_language.get(file_row.language, 0) + 1

    rows = SymbolRepository(connection).list_for_project(project_id)
    by_type: dict[str, int] = {}
    for row in rows:
        by_type[row.symbol_type] = by_type.get(row.symbol_type, 0) + 1
    namespaces = int(connection.execute(
        "SELECT COUNT(*) FROM namespaces n JOIN files f ON f.file_id = n.file_id "
        "WHERE f.project_id = ?",
        (project_id,),
    ).fetchone()[0])
    parser_failures = sum(1 for file_row in files if file_row.scan_status == "failed")

    scans = ScanHistoryRepository(connection).list_recent(project_id, limit=10)
    entries = [
        ScanHistoryEntry(
            scan_id=int(scan.scan_id),
            scan_type=scan.scan_type,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            duration_seconds=(
                scan.completed_at - scan.started_at
                if scan.completed_at is not None else None
            ),
            files_processed=scan.files_processed,
            symbols_added=scan.symbols_added,
            status=scan.status,
        )
        for scan in scans
    ]
    return IndexStatisticsTool(
        total_files=len(files),
        files_by_language=by_language,
        total_symbols=len(rows),
        symbols_by_type=by_type,
        namespaces=namespaces,
        parser_failures=parser_failures,
        recent_scans=entries,
    )
