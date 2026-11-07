"""Schema creation and versioned migrations.

The schema version is stored in SQLite's ``PRAGMA user_version``. Each
migration is a plain SQL script that is applied atomically (BEGIN … COMMIT
includes the version bump), so a failed migration leaves the previous schema
and data untouched. Before an existing database is upgraded, a backup copy is
written beside it (PLAN.md §18.1).

Migration scripts must not contain semicolons inside string literals; the
version bump is appended to the script verbatim.
"""

import shutil
import sqlite3
from pathlib import Path

from cii.core.exceptions import MigrationError

SCHEMA_VERSION = 1


_INITIAL_SCHEMA = """
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    project_root TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_scan REAL,
    index_version TEXT NOT NULL,
    configuration_hash TEXT NOT NULL
);

CREATE TABLE files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    language TEXT NOT NULL,
    content_hash TEXT,
    file_size INTEGER,
    modified_at REAL,
    last_scanned REAL,
    scan_status TEXT NOT NULL DEFAULT 'pending',
    parser_version TEXT,
    UNIQUE (project_id, relative_path)
);
CREATE INDEX idx_files_project ON files (project_id);
CREATE INDEX idx_files_hash ON files (content_hash);
CREATE INDEX idx_files_status ON files (scan_status);

CREATE TABLE symbols (
    symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    parent_symbol_id INTEGER REFERENCES symbols(symbol_id) ON DELETE SET NULL,
    symbol_name TEXT NOT NULL,
    fully_qualified_name TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'unknown',
    signature TEXT,
    start_line INTEGER,
    end_line INTEGER,
    fingerprint TEXT
);
CREATE INDEX idx_symbols_file ON symbols (file_id);
CREATE INDEX idx_symbols_name ON symbols (symbol_name);
CREATE INDEX idx_symbols_fqn ON symbols (fully_qualified_name);
CREATE INDEX idx_symbols_type ON symbols (symbol_type);

CREATE TABLE namespaces (
    namespace_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    namespace_name TEXT NOT NULL,
    parent_namespace_id INTEGER REFERENCES namespaces(namespace_id) ON DELETE SET NULL
);
CREATE INDEX idx_namespaces_file ON namespaces (file_id);
CREATE INDEX idx_namespaces_name ON namespaces (namespace_name);

CREATE TABLE relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id) ON DELETE CASCADE,
    target_symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    resolution_status TEXT NOT NULL DEFAULT 'resolved',
    UNIQUE (source_symbol_id, target_symbol_id, relationship_type)
);
CREATE INDEX idx_rel_source ON relationships (source_symbol_id);
CREATE INDEX idx_rel_target ON relationships (target_symbol_id);

CREATE TABLE scan_history (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    scan_type TEXT NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    files_processed INTEGER NOT NULL DEFAULT 0,
    files_failed INTEGER NOT NULL DEFAULT 0,
    symbols_added INTEGER NOT NULL DEFAULT 0,
    symbols_updated INTEGER NOT NULL DEFAULT 0,
    symbols_removed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running'
);
CREATE INDEX idx_scan_history_project ON scan_history (project_id);

CREATE TABLE integrity_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    validation_time REAL NOT NULL,
    files_checked INTEGER NOT NULL DEFAULT 0,
    errors_found INTEGER NOT NULL DEFAULT 0,
    warnings_found INTEGER NOT NULL DEFAULT 0,
    report_status TEXT NOT NULL
);
CREATE INDEX idx_integrity_reports_project ON integrity_reports (project_id);
"""

# (target_version, SQL script) applied in ascending version order. Plain SQL
# only; Python-level data migrations can be added here when needed.
MIGRATIONS: list[tuple[int, str]] = [
    (1, _INITIAL_SCHEMA),
]


def schema_version(connection: sqlite3.Connection) -> int:
    """Return the schema version recorded in the database."""
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def backup_database(db_path: Path, version: int) -> Path:
    """Copy the database file to a versioned backup beside it."""
    backup_path = db_path.with_name(f"{db_path.name}.backup-v{version}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_migrations(
    connection: sqlite3.Connection, db_path: Path | None = None
) -> list[int]:
    """Bring the database up to :data:`SCHEMA_VERSION`.

    Returns the list of applied migration versions (empty when already up to
    date). When an existing database is upgraded and ``db_path`` is provided,
    a backup copy is written first.

    Raises:
        MigrationError: the database is newer than this build understands, or
            a migration failed (the database is left at its previous version).
    """
    current = schema_version(connection)
    if current > SCHEMA_VERSION:
        raise MigrationError(
            f"database schema version {current} is newer than supported {SCHEMA_VERSION}"
        )
    pending = [(version, script) for version, script in MIGRATIONS if version > current]
    if pending and current > 0 and db_path is not None and db_path.is_file():
        backup_database(db_path, current)

    applied: list[int] = []
    for version, script in pending:
        script_with_version = (
            "BEGIN;\n" + script + f"\nPRAGMA user_version = {version};\nCOMMIT;\n"
        )
        try:
            connection.executescript(script_with_version)
        except sqlite3.Error as error:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass  # best-effort cleanup of the primary migration error
            raise MigrationError(f"migration to version {version} failed: {error}") from error
        applied.append(version)
    return applied
