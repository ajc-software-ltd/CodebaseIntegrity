"""Tests for database lifecycle, migrations, and health checks."""

import sqlite3
from pathlib import Path

import pytest

from cii.core.exceptions import MigrationError
from cii.database import migrations
from cii.database.database import DATABASE_FILE_NAME, Database
from cii.database.migrations import SCHEMA_VERSION, apply_migrations, schema_version


class TestDatabaseOpen:
    def test_creates_database_and_schema(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            assert database.path == project_root / ".cii" / DATABASE_FILE_NAME
            assert database.schema_version() == SCHEMA_VERSION
            tables = {
                row[0]
                for row in database.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert {"projects", "files", "symbols", "namespaces", "relationships",
                    "scan_history", "integrity_reports"} <= tables

    def test_reopen_is_stable(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            connection = database.connection
            connection.execute(
                "INSERT INTO projects (project_id, project_name, project_root, created_at,"
                " index_version, configuration_hash) VALUES ('p1', 'x', '/x', 0, '1.0', 'h')"
            )
        with Database.open(project_root) as database:
            assert database.schema_version() == SCHEMA_VERSION
            row = database.connection.execute("SELECT COUNT(*) FROM projects").fetchone()
            assert row[0] == 1

    def test_pragmas_applied(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            assert database.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert database.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


class TestHealthCheck:
    def test_healthy_database(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            health = database.health_check()
            assert health.ok is True
            assert health.integrity_check == "ok"
            assert health.foreign_key_violations == 0
            assert health.schema_version == SCHEMA_VERSION

    def test_unsupported_schema_reports_not_ok(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            database.connection.execute("PRAGMA user_version = 99")
            health = database.health_check()
            assert health.ok is False
            assert health.schema_version == 99


class TestMigrations:
    def test_newer_schema_rejected(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        try:
            connection.execute("PRAGMA user_version = 99")
            with pytest.raises(MigrationError, match="newer than supported"):
                apply_migrations(connection)
        finally:
            connection.close()

    def test_failed_migration_is_atomic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        try:
            monkeypatch.setattr(
                migrations,
                "MIGRATIONS",
                [(1, "CREATE TABLE a (x INTEGER); THIS IS NOT SQL;")],
            )
            with pytest.raises(MigrationError, match="migration to version 1 failed"):
                apply_migrations(connection)
            assert schema_version(connection) == 0
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            assert "a" not in tables
        finally:
            connection.close()

    def test_upgrade_creates_backup(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with Database.open(project_root) as database:
            db_path = database.path
            assert db_path.is_file()
            monkeypatch.setattr(
                migrations,
                "MIGRATIONS",
                list(migrations.MIGRATIONS)
                + [(2, "ALTER TABLE projects ADD COLUMN note TEXT;")],
            )
            monkeypatch.setattr(migrations, "SCHEMA_VERSION", 2)
            applied = apply_migrations(database.connection, db_path)
            assert applied == [2]
            assert (db_path.parent / f"{DATABASE_FILE_NAME}.backup-v1").is_file()
            assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 2
