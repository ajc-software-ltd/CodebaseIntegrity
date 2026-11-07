"""SQLite database lifecycle.

The database lives at ``<project-root>/.cii/cii.db`` and is the authoritative
store for the structural index (PLAN.md §6). Connections run in autocommit
mode with explicit transactions (see :mod:`cii.database.transactions`), WAL
journalling, and enforced foreign keys.

MCP tool handlers execute on worker threads (MCP SDK v2), so the connection
is opened with ``check_same_thread=False`` and every cross-thread operation
runs under the database's reentrant lock (:meth:`Database.locked`) — one
logical operation at a time, keeping savepoint transactions un-interleaved.

A failed scan must never corrupt the previous valid index: writes are
transactional, migrations are atomic, and :meth:`Database.health_check`
exposes integrity state to callers.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from cii.core.exceptions import DatabaseError, PathSecurityError
from cii.database.migrations import SCHEMA_VERSION, apply_migrations, schema_version
from cii.database.models import HealthReport
from cii.utilities.paths import cii_data_dir, is_within_root

DATABASE_FILE_NAME = "cii.db"
_BUSY_TIMEOUT_MS = 5000


class Database:
    """A connection to one project's CII database."""

    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self._connection = connection
        self._path = path
        self._lock = threading.RLock()

    @classmethod
    def open(cls, project_root: Path) -> "Database":
        """Open (creating if necessary) the database under ``project_root``.

        Raises:
            PathSecurityError: the database path would escape the project root.
            DatabaseError: the file exists but is not a usable SQLite database.
        """
        data_dir = cii_data_dir(project_root)
        db_path = data_dir / DATABASE_FILE_NAME
        if not is_within_root(db_path, project_root):
            raise PathSecurityError(f"database path escapes the project root: {db_path}")
        data_dir.mkdir(parents=True, exist_ok=True)

        try:
            connection = sqlite3.connect(
                db_path, isolation_level=None, check_same_thread=False
            )
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.Error as error:
            raise DatabaseError(f"cannot open database {db_path}: {error}") from error

        try:
            apply_migrations(connection, db_path)
        except Exception:
            connection.close()
            raise
        return cls(connection, db_path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    @contextmanager
    def locked(self):
        """Serialize one logical operation across handler threads (reentrant)."""
        with self._lock:
            yield self

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def schema_version(self) -> int:
        """Return the schema version of the open database."""
        return schema_version(self._connection)

    def health_check(self) -> HealthReport:
        """Run integrity, foreign-key, and schema checks (PLAN.md §18.1)."""
        try:
            integrity = self._connection.execute("PRAGMA integrity_check").fetchone()[0]
            violations = len(self._connection.execute("PRAGMA foreign_key_check").fetchall())
            journal_mode = self._connection.execute("PRAGMA journal_mode").fetchone()[0]
            version = schema_version(self._connection)
            ok = integrity == "ok" and violations == 0 and version == SCHEMA_VERSION
            return HealthReport(
                ok=ok,
                schema_version=version,
                journal_mode=journal_mode,
                integrity_check=integrity,
                foreign_key_violations=violations,
            )
        except sqlite3.Error as error:
            return HealthReport(
                ok=False,
                schema_version=0,
                journal_mode="unknown",
                integrity_check="error",
                foreign_key_violations=0,
                error=str(error),
            )
