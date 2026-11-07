"""Database internal consistency checks (PLAN.md §10.1).

Covers schema health (integrity check, foreign keys, schema version) and
structural coherence of the index rows themselves: failed/pending files and
parent links that cross file boundaries (the index pipeline only links
symbols within one file).
"""

from cii.core.enums import FindingSeverity
from cii.core.models import IntegrityFinding
from cii.database.database import Database
from cii.database.migrations import SCHEMA_VERSION
from cii.database.models import SymbolRow
from cii.database.repositories import FileRepository, SymbolRepository


def check_database(database: Database) -> list[IntegrityFinding]:
    """Schema-level checks: integrity, foreign keys, schema version."""
    findings: list[IntegrityFinding] = []
    health = database.health_check()
    if health.error is not None:
        findings.append(IntegrityFinding(
            code="database_inconsistency",
            severity=FindingSeverity.ERROR,
            message=f"database health check failed: {health.error}",
        ))
        return findings
    if health.integrity_check != "ok":
        findings.append(IntegrityFinding(
            code="database_inconsistency",
            severity=FindingSeverity.ERROR,
            message=f"SQLite integrity check reports: {health.integrity_check}",
        ))
    if health.foreign_key_violations:
        findings.append(IntegrityFinding(
            code="database_inconsistency",
            severity=FindingSeverity.ERROR,
            message=f"{health.foreign_key_violations} foreign-key violation(s) present",
        ))
    if health.schema_version != SCHEMA_VERSION:
        findings.append(IntegrityFinding(
            code="database_inconsistency",
            severity=FindingSeverity.ERROR,
            message=(
                f"schema version {health.schema_version} does not match "
                f"expected {SCHEMA_VERSION}"
            ),
        ))
    return findings


def check_index_rows(database: Database, project_id: str) -> list[IntegrityFinding]:
    """Row-level coherence: failed/pending files and cross-file parent links."""
    findings: list[IntegrityFinding] = []
    file_repo = FileRepository(database.connection)
    symbol_repo = SymbolRepository(database.connection)

    for file_row in file_repo.list_all(project_id):
        if file_row.scan_status == "failed":
            findings.append(IntegrityFinding(
                code="parser_failure",
                severity=FindingSeverity.WARNING,
                message=(
                    f"file failed parsing with {file_row.parser_version or 'unknown parser'} "
                    "(previous index retained)"
                ),
                file_path=file_row.relative_path,
            ))
        elif file_row.scan_status == "pending":
            findings.append(IntegrityFinding(
                code="pending_index",
                severity=FindingSeverity.WARNING,
                message="file is discovered but not yet indexed",
                file_path=file_row.relative_path,
            ))
        elif file_row.scan_status == "unsupported":
            findings.append(IntegrityFinding(
                code="unsupported_file",
                severity=FindingSeverity.WARNING,
                message="file has no parser for its language",
                file_path=file_row.relative_path,
            ))

    file_by_id = {
        int(file_row.file_id): file_row.relative_path
        for file_row in file_repo.list_all(project_id)
        if file_row.file_id is not None
    }
    for symbol_row in symbol_repo.list_for_project(project_id):
        if symbol_row.parent_symbol_id is None or symbol_row.file_id is None:
            continue
        parent = _symbol_by_id(database, int(symbol_row.parent_symbol_id))
        if parent is not None and parent.file_id != symbol_row.file_id:
            findings.append(IntegrityFinding(
                code="inconsistent_parent",
                severity=FindingSeverity.WARNING,
                message=(
                    f"symbol '{symbol_row.fully_qualified_name}' has a parent symbol "
                    "in a different file"
                ),
                file_path=file_by_id.get(int(symbol_row.file_id)),
                symbol=symbol_row.fully_qualified_name,
            ))
    return findings


def _symbol_by_id(database: Database, symbol_id: int) -> SymbolRow | None:
    row = database.connection.execute(
        "SELECT * FROM symbols WHERE symbol_id = ?", (symbol_id,)
    ).fetchone()
    return SymbolRow(**dict(row)) if row is not None else None
