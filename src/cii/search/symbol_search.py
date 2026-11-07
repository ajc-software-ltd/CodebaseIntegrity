"""Symbol and namespace search (PLAN.md §11).

Concise by default: results carry identity and location, and only expand to
signatures, line numbers and freshness details on request. Every query is
paginated (``total``/``offset``/``limit``) so large indexes never flood the
caller's context (PLAN.md §17.3).

Matching: a query matches a symbol when it equals the simple name or the
fully qualified name, or when either contains the query (case-insensitive).
Results rank exact simple-name matches first, then exact fully qualified
matches, then substring matches — deterministic within each rank.

Namespace attribution is derived from the file's recorded namespace
declarations (longest fully qualified prefix) — the symbols table follows the
PLAN.md §6.2 schema and stores no separate namespace column.
"""

from pydantic import BaseModel, Field

from cii.core.models import SymbolCounts
from cii.database.database import Database


class SymbolSearchHit(BaseModel):
    """One symbol located by search."""

    name: str
    fully_qualified_name: str
    symbol_type: str
    file_path: str
    namespace: str | None = None
    parent: str | None = None
    file_status: str = "indexed"
    # expanded-only fields
    visibility: str | None = None
    signature: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    last_scanned: float | None = None


class SymbolSearchPage(BaseModel):
    """Paginated symbol search response."""

    total: int
    offset: int
    limit: int
    results: list[SymbolSearchHit]


class NamespaceSearchHit(BaseModel):
    name: str
    file_path: str
    parent_name: str | None = None


class FileStructure(BaseModel):
    """Structural overview of one file (MCP tool `index_file`)."""

    file_path: str
    language: str
    file_status: str
    last_scanned: float | None = None
    counts: SymbolCounts = Field(default_factory=SymbolCounts)
    namespaces: list[str] = []
    symbols: list[SymbolSearchHit] = []


_SELECT = (
    "SELECT s.*, f.relative_path AS file_path, f.scan_status, f.last_scanned, "
    " (SELECT p.symbol_name FROM symbols p WHERE p.symbol_id = s.parent_symbol_id) "
    " AS parent_name "
    "FROM symbols s JOIN files f ON f.file_id = s.file_id "
)


def search_symbols(
    database: Database,
    project_id: str,
    query: str,
    *,
    symbol_type: str | None = None,
    language: str | None = None,
    limit: int = 20,
    offset: int = 0,
    expanded: bool = False,
) -> SymbolSearchPage:
    """Search indexed symbols by name/fqn with optional filters."""
    like = f"%{query.lower()}%"
    where = [
        "f.project_id = ?",
        "(LOWER(s.symbol_name) = ? OR LOWER(s.fully_qualified_name) = ? "
        "OR LOWER(s.symbol_name) LIKE ? OR LOWER(s.fully_qualified_name) LIKE ?)",
    ]
    params: list[object] = [project_id, query.lower(), query.lower(), like, like]
    if symbol_type is not None:
        where.append("s.symbol_type = ?")
        params.append(symbol_type)
    if language is not None:
        where.append("f.language = ?")
        params.append(language)
    where_sql = " AND ".join(where)

    total = int(database.connection.execute(
        "SELECT COUNT(*) FROM symbols s JOIN files f ON f.file_id = s.file_id "
        f"WHERE {where_sql}",
        params,
    ).fetchone()[0])
    rows = database.connection.execute(
        _SELECT + f"WHERE {where_sql} "
        "ORDER BY CASE "
        "  WHEN LOWER(s.symbol_name) = ? THEN 0 "
        "  WHEN LOWER(s.fully_qualified_name) = ? THEN 1 "
        "  ELSE 2 END, s.fully_qualified_name, s.symbol_id "
        "LIMIT ? OFFSET ?",
        [*params, query.lower(), query.lower(), limit, offset],
    ).fetchall()

    namespaces_by_file = _namespaces_by_file(database, [row["file_id"] for row in rows])
    results = [
        _hit_from_row(row, expanded=expanded, namespaces_by_file=namespaces_by_file)
        for row in rows
    ]
    return SymbolSearchPage(total=total, offset=offset, limit=limit, results=results)


def search_namespaces(
    database: Database, project_id: str, query: str, *, limit: int = 20, offset: int = 0
) -> list[NamespaceSearchHit]:
    """Search namespace declarations by name (substring, case-insensitive)."""
    like = f"%{query.lower()}%"
    rows = database.connection.execute(
        "SELECT n.*, f.relative_path AS file_path, "
        " (SELECT q.namespace_name FROM namespaces q "
        "  WHERE q.namespace_id = n.parent_namespace_id) AS parent_name "
        "FROM namespaces n JOIN files f ON f.file_id = n.file_id "
        "WHERE f.project_id = ? AND LOWER(n.namespace_name) LIKE ? "
        "ORDER BY n.namespace_name, f.relative_path LIMIT ? OFFSET ?",
        (project_id, like, limit, offset),
    ).fetchall()
    return [
        NamespaceSearchHit(
            name=row["namespace_name"],
            file_path=row["file_path"],
            parent_name=row["parent_name"],
        )
        for row in rows
    ]


def file_structure(
    database: Database, project_id: str, relative_path: str
) -> FileStructure | None:
    """Structural overview of one file (names, counts, symbols ordered by line)."""
    file_row = database.connection.execute(
        "SELECT * FROM files WHERE project_id = ? AND relative_path = ?",
        (project_id, relative_path),
    ).fetchone()
    if file_row is None:
        return None

    symbol_rows = database.connection.execute(
        _SELECT + "WHERE s.file_id = ? ORDER BY s.start_line, s.symbol_id",
        (file_row["file_id"],),
    ).fetchall()
    namespace_rows = database.connection.execute(
        "SELECT * FROM namespaces WHERE file_id = ? ORDER BY namespace_id",
        (file_row["file_id"],),
    ).fetchall()
    from cii.indexer.symbol_extractor import compute_counts

    counts = compute_counts(
        (row["symbol_type"] for row in symbol_rows), len(namespace_rows)
    )
    namespaces_by_file = {file_row["file_id"]: [r["namespace_name"] for r in namespace_rows]}
    return FileStructure(
        file_path=relative_path,
        language=file_row["language"],
        file_status=file_row["scan_status"],
        last_scanned=file_row["last_scanned"],
        counts=counts,
        namespaces=[row["namespace_name"] for row in namespace_rows],
        symbols=[
            _hit_from_row(row, expanded=True, namespaces_by_file=namespaces_by_file)
            for row in symbol_rows
        ],
    )


def _namespaces_by_file(database: Database, file_ids: list[int]) -> dict[int, list[str]]:
    unique = sorted({int(file_id) for file_id in file_ids})
    if not unique:
        return {}
    placeholders = ", ".join("?" for _ in unique)
    rows = database.connection.execute(
        f"SELECT file_id, namespace_name FROM namespaces "
        f"WHERE file_id IN ({placeholders}) ORDER BY namespace_name",
        unique,
    ).fetchall()
    mapping: dict[int, list[str]] = {}
    for row in rows:
        mapping.setdefault(int(row["file_id"]), []).append(row["namespace_name"])
    return mapping


def _namespace_of(fully_qualified_name: str, candidates: list[str]) -> str | None:
    """Longest namespace declaration that is a prefix of the fully qualified name."""
    best: str | None = None
    for name in candidates:
        if fully_qualified_name == name:
            continue
        if fully_qualified_name.startswith(name + "::") or fully_qualified_name.startswith(
            name + "."
        ):
            if best is None or len(name) > len(best):
                best = name
    return best


def _hit_from_row(row, *, expanded: bool, namespaces_by_file: dict[int, list[str]]):  # type: ignore[no-untyped-def]
    namespace = _namespace_of(
        row["fully_qualified_name"], namespaces_by_file.get(int(row["file_id"]), [])
    )
    base = SymbolSearchHit(
        name=row["symbol_name"],
        fully_qualified_name=row["fully_qualified_name"],
        symbol_type=row["symbol_type"],
        file_path=row["file_path"],
        namespace=namespace,
        parent=row["parent_name"],
        file_status=row["scan_status"],
    )
    if expanded:
        return base.model_copy(update={
            "visibility": row["visibility"],
            "signature": row["signature"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "last_scanned": row["last_scanned"],
        })
    return base
