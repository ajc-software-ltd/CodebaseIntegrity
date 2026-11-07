"""Repository layer: typed access to the CII schema tables.

Repositories execute SQL against a shared connection. Multi-statement
operations manage their own atomicity through savepoint transactions and can
therefore be nested inside a caller's larger transaction (for example a whole
scan cycle).

Domain models live in :mod:`cii.core.models`; row models mirror the schema and
are defined in :mod:`cii.database.models`. Row surrogate keys are ``None`` on
input and populated on returned rows.
"""

import sqlite3
import time
import uuid
from collections.abc import Sequence
from typing import TypeVar

from cii.core.models import NamespaceInput, SymbolInfo
from cii.database.models import (
    FileRow,
    IntegrityReportRow,
    NamespaceRow,
    ProjectRow,
    RelationshipRow,
    ScanHistoryRow,
    SymbolRow,
)
from cii.database.transactions import transaction

_ModelT = TypeVar("_ModelT")


def _map(model: type[_ModelT], row: sqlite3.Row | None) -> _ModelT | None:
    return model(**dict(row)) if row is not None else None  # type: ignore[arg-type]


def _map_all(model: type[_ModelT], rows: list[sqlite3.Row]) -> list[_ModelT]:
    return [model(**dict(row)) for row in rows]  # type: ignore[arg-type]


class ProjectRepository:
    """``projects`` table access."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def register(
        self,
        project_name: str,
        project_root: str,
        index_version: str,
        configuration_hash: str,
    ) -> ProjectRow:
        """Register a project, or update an existing registration in place.

        Registration is keyed by project root, so repeated ``cii init`` runs
        keep a single record per project.
        """
        existing = self.get_by_root(project_root)
        with transaction(self._connection):
            if existing is not None:
                self._connection.execute(
                    "UPDATE projects SET project_name = ?, index_version = ?, "
                    "configuration_hash = ? WHERE project_id = ?",
                    (project_name, index_version, configuration_hash, existing.project_id),
                )
                project_id = existing.project_id
            else:
                project_id = uuid.uuid4().hex
                self._connection.execute(
                    "INSERT INTO projects (project_id, project_name, project_root, "
                    "created_at, last_scan, index_version, configuration_hash) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?)",
                    (
                        project_id,
                        project_name,
                        project_root,
                        time.time(),
                        index_version,
                        configuration_hash,
                    ),
                )
        row = self.get(project_id)
        assert row is not None
        return row

    def get(self, project_id: str) -> ProjectRow | None:
        row = self._connection.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return _map(ProjectRow, row)

    def get_by_root(self, project_root: str) -> ProjectRow | None:
        row = self._connection.execute(
            "SELECT * FROM projects WHERE project_root = ?", (project_root,)
        ).fetchone()
        return _map(ProjectRow, row)

    def list_all(self) -> list[ProjectRow]:
        rows = self._connection.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return _map_all(ProjectRow, rows)

    def set_last_scan(self, project_id: str, when: float | None = None) -> None:
        self._connection.execute(
            "UPDATE projects SET last_scan = ? WHERE project_id = ?",
            (when if when is not None else time.time(), project_id),
        )


class FileRepository:
    """``files`` table access."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(self, row: FileRow) -> FileRow:
        """Insert or update a file record.

        Keyed by ``file_id`` when provided (path-preserving updates such as
        renames), otherwise by (project, relative path).
        """
        with transaction(self._connection):
            if row.file_id is not None:
                existing = self._get_by_id(row.file_id)
            else:
                existing = self.get_by_path(row.project_id, row.relative_path)
            if existing is not None and existing.file_id is not None:
                self._connection.execute(
                    "UPDATE files SET relative_path = ?, filename = ?, extension = ?, "
                    "language = ?, content_hash = ?, file_size = ?, modified_at = ?, "
                    "last_scanned = ?, scan_status = ?, parser_version = ? WHERE file_id = ?",
                    (
                        row.relative_path,
                        row.filename,
                        row.extension,
                        row.language,
                        row.content_hash,
                        row.file_size,
                        row.modified_at,
                        row.last_scanned,
                        row.scan_status,
                        row.parser_version,
                        existing.file_id,
                    ),
                )
                updated = self._get_by_id(existing.file_id)
                assert updated is not None
                return updated
            cursor = self._connection.execute(
                "INSERT INTO files (project_id, relative_path, filename, extension, "
                "language, content_hash, file_size, modified_at, last_scanned, "
                "scan_status, parser_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row.project_id,
                    row.relative_path,
                    row.filename,
                    row.extension,
                    row.language,
                    row.content_hash,
                    row.file_size,
                    row.modified_at,
                    row.last_scanned,
                    row.scan_status,
                    row.parser_version,
                ),
            )
            inserted = self._get_by_id(int(cursor.lastrowid))
            assert inserted is not None
            return inserted

    def _get_by_id(self, file_id: int) -> FileRow | None:
        row = self._connection.execute(
            "SELECT * FROM files WHERE file_id = ?", (file_id,)
        ).fetchone()
        return _map(FileRow, row)

    def get_by_path(self, project_id: str, relative_path: str) -> FileRow | None:
        row = self._connection.execute(
            "SELECT * FROM files WHERE project_id = ? AND relative_path = ?",
            (project_id, relative_path),
        ).fetchone()
        return _map(FileRow, row)

    def list_all(self, project_id: str) -> list[FileRow]:
        rows = self._connection.execute(
            "SELECT * FROM files WHERE project_id = ? ORDER BY relative_path", (project_id,)
        ).fetchall()
        return _map_all(FileRow, rows)

    def delete(self, project_id: str, relative_path: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM files WHERE project_id = ? AND relative_path = ?",
            (project_id, relative_path),
        )
        return cursor.rowcount > 0

    def find_by_content_hash(self, project_id: str, content_hash: str) -> list[FileRow]:
        """Find files by content fingerprint (rename/move detection)."""
        rows = self._connection.execute(
            "SELECT * FROM files WHERE project_id = ? AND content_hash = ? "
            "ORDER BY relative_path",
            (project_id, content_hash),
        ).fetchall()
        return _map_all(FileRow, rows)

    def count_by_status(self, project_id: str, scan_status: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM files WHERE project_id = ? AND scan_status = ?",
            (project_id, scan_status),
        ).fetchone()
        return int(row[0])


class SymbolRepository:
    """``symbols`` table access."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace_for_file(self, file_id: int, symbols: Sequence[SymbolInfo]) -> int:
        """Atomically replace all symbols of one file.

        Previous rows for the file (and relationships that reference them)
        are removed and the new set inserted inside a single transaction, so a
        failed scan cannot corrupt the previous valid index. Parent links are
        resolved by fully qualified name within the file. Returns the number
        of symbols inserted.
        """
        with transaction(self._connection):
            self._connection.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
            ids_by_fqn: dict[str, int] = {}
            for symbol in symbols:
                cursor = self._connection.execute(
                    "INSERT INTO symbols (file_id, parent_symbol_id, symbol_name, "
                    "fully_qualified_name, symbol_type, visibility, signature, "
                    "start_line, end_line, fingerprint) "
                    "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        file_id,
                        symbol.name,
                        symbol.fully_qualified_name,
                        symbol.symbol_type.value,
                        symbol.visibility.value,
                        symbol.signature,
                        symbol.start_line,
                        symbol.end_line,
                        symbol.fingerprint,
                    ),
                )
                ids_by_fqn[symbol.fully_qualified_name] = int(cursor.lastrowid)
            for symbol in symbols:
                if symbol.parent and symbol.parent in ids_by_fqn:
                    self._connection.execute(
                        "UPDATE symbols SET parent_symbol_id = ? WHERE symbol_id = ?",
                        (ids_by_fqn[symbol.parent], ids_by_fqn[symbol.fully_qualified_name]),
                    )
        return len(symbols)

    def list_by_file(self, file_id: int) -> list[SymbolRow]:
        rows = self._connection.execute(
            "SELECT * FROM symbols WHERE file_id = ? ORDER BY start_line, symbol_id", (file_id,)
        ).fetchall()
        return _map_all(SymbolRow, rows)

    def list_by_name(self, symbol_name: str, project_id: str | None = None) -> list[SymbolRow]:
        if project_id is None:
            rows = self._connection.execute(
                "SELECT * FROM symbols WHERE symbol_name = ? ORDER BY fully_qualified_name",
                (symbol_name,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT s.* FROM symbols s JOIN files f ON f.file_id = s.file_id "
                "WHERE s.symbol_name = ? AND f.project_id = ? ORDER BY s.fully_qualified_name",
                (symbol_name, project_id),
            ).fetchall()
        return _map_all(SymbolRow, rows)

    def list_by_fully_qualified_name(
        self, fully_qualified_name: str, project_id: str | None = None
    ) -> list[SymbolRow]:
        """Return all symbols with the given fully qualified name (overloads)."""
        if project_id is None:
            rows = self._connection.execute(
                "SELECT * FROM symbols WHERE fully_qualified_name = ? ORDER BY symbol_id",
                (fully_qualified_name,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT s.* FROM symbols s JOIN files f ON f.file_id = s.file_id "
                "WHERE s.fully_qualified_name = ? AND f.project_id = ? ORDER BY s.symbol_id",
                (fully_qualified_name, project_id),
            ).fetchall()
        return _map_all(SymbolRow, rows)

    def count_for_project(self, project_id: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM symbols s JOIN files f ON f.file_id = s.file_id "
            "WHERE f.project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row[0])


class NamespaceRepository:
    """``namespaces`` table access (per-file namespace declarations)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace_for_file(self, file_id: int, namespaces: Sequence[NamespaceInput]) -> int:
        """Atomically replace the namespace declarations of one file.

        Parent links are resolved by namespace name within the file.
        """
        with transaction(self._connection):
            self._connection.execute("DELETE FROM namespaces WHERE file_id = ?", (file_id,))
            ids_by_name: dict[str, int] = {}
            for entry in namespaces:
                cursor = self._connection.execute(
                    "INSERT INTO namespaces (file_id, namespace_name, parent_namespace_id) "
                    "VALUES (?, ?, NULL)",
                    (file_id, entry.namespace_name),
                )
                ids_by_name.setdefault(entry.namespace_name, int(cursor.lastrowid))
            for entry in namespaces:
                if entry.parent_name and entry.parent_name in ids_by_name:
                    self._connection.execute(
                        "UPDATE namespaces SET parent_namespace_id = ? WHERE namespace_id = ?",
                        (
                            ids_by_name[entry.parent_name],
                            ids_by_name[entry.namespace_name],
                        ),
                    )
        return len(namespaces)

    def list_by_file(self, file_id: int) -> list[NamespaceRow]:
        rows = self._connection.execute(
            "SELECT * FROM namespaces WHERE file_id = ? ORDER BY namespace_id", (file_id,)
        ).fetchall()
        return _map_all(NamespaceRow, rows)


class RelationshipRepository:
    """``relationships`` table access.

    Relationships are only recorded when supported by parser or
    semantic-analysis evidence (PLAN.md §6.2).
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(
        self,
        source_symbol_id: int,
        target_symbol_id: int,
        relationship_type: str,
        confidence: float = 1.0,
        resolution_status: str = "resolved",
    ) -> RelationshipRow:
        """Record a relationship; duplicates return the existing row."""
        with transaction(self._connection):
            self._connection.execute(
                "INSERT OR IGNORE INTO relationships (source_symbol_id, target_symbol_id, "
                "relationship_type, confidence, resolution_status) VALUES (?, ?, ?, ?, ?)",
                (
                    source_symbol_id,
                    target_symbol_id,
                    relationship_type,
                    confidence,
                    resolution_status,
                ),
            )
        rows = self._connection.execute(
            "SELECT * FROM relationships WHERE source_symbol_id = ? AND target_symbol_id = ? "
            "AND relationship_type = ?",
            (source_symbol_id, target_symbol_id, relationship_type),
        ).fetchone()
        row = _map(RelationshipRow, rows)
        assert row is not None
        return row

    def list_for_symbol(
        self, symbol_id: int, relationship_types: Sequence[str] | None = None
    ) -> list[RelationshipRow]:
        """Return relationships where the symbol is source or target."""
        query = (
            "SELECT * FROM relationships WHERE (source_symbol_id = ? OR target_symbol_id = ?)"
        )
        params: list[object] = [symbol_id, symbol_id]
        if relationship_types:
            placeholders = ", ".join("?" for _ in relationship_types)
            query += f" AND relationship_type IN ({placeholders})"
            params.extend(relationship_types)
        query += " ORDER BY relationship_id"
        rows = self._connection.execute(query, params).fetchall()
        return _map_all(RelationshipRow, rows)


class ScanHistoryRepository:
    """``scan_history`` table access."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def start(
        self, project_id: str, scan_type: str, started_at: float | None = None
    ) -> ScanHistoryRow:
        cursor = self._connection.execute(
            "INSERT INTO scan_history (project_id, scan_type, started_at, status) "
            "VALUES (?, ?, ?, 'running')",
            (project_id, scan_type, started_at if started_at is not None else time.time()),
        )
        row = self._get_by_id(int(cursor.lastrowid))
        assert row is not None
        return row

    def finish(
        self,
        scan_id: int,
        *,
        completed_at: float | None = None,
        files_processed: int = 0,
        files_failed: int = 0,
        symbols_added: int = 0,
        symbols_updated: int = 0,
        symbols_removed: int = 0,
        status: str = "completed",
    ) -> ScanHistoryRow:
        self._connection.execute(
            "UPDATE scan_history SET completed_at = ?, files_processed = ?, files_failed = ?, "
            "symbols_added = ?, symbols_updated = ?, symbols_removed = ?, status = ? "
            "WHERE scan_id = ?",
            (
                completed_at if completed_at is not None else time.time(),
                files_processed,
                files_failed,
                symbols_added,
                symbols_updated,
                symbols_removed,
                status,
                scan_id,
            ),
        )
        row = self._get_by_id(scan_id)
        assert row is not None
        return row

    def _get_by_id(self, scan_id: int) -> ScanHistoryRow | None:
        row = self._connection.execute(
            "SELECT * FROM scan_history WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        return _map(ScanHistoryRow, row)

    def list_recent(self, project_id: str, limit: int = 10) -> list[ScanHistoryRow]:
        rows = self._connection.execute(
            "SELECT * FROM scan_history WHERE project_id = ? ORDER BY scan_id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return _map_all(ScanHistoryRow, rows)


class IntegrityReportRepository:
    """``integrity_reports`` table access."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(
        self,
        project_id: str,
        report_status: str,
        *,
        validation_time: float | None = None,
        files_checked: int = 0,
        errors_found: int = 0,
        warnings_found: int = 0,
    ) -> IntegrityReportRow:
        cursor = self._connection.execute(
            "INSERT INTO integrity_reports (project_id, validation_time, files_checked, "
            "errors_found, warnings_found, report_status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                validation_time if validation_time is not None else time.time(),
                files_checked,
                errors_found,
                warnings_found,
                report_status,
            ),
        )
        row = self._connection.execute(
            "SELECT * FROM integrity_reports WHERE report_id = ?", (int(cursor.lastrowid),)
        ).fetchone()
        result = _map(IntegrityReportRow, row)
        assert result is not None
        return result

    def list_recent(self, project_id: str, limit: int = 10) -> list[IntegrityReportRow]:
        rows = self._connection.execute(
            "SELECT * FROM integrity_reports WHERE project_id = ? "
            "ORDER BY report_id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return _map_all(IntegrityReportRow, rows)
