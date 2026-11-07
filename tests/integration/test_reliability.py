"""Reliability and recovery tests (PLAN.md §18, §21 M12).

Database recovery (rollback, backups, rebuild-from-source) and parser failure
recovery verified end-to-end against real project trees.
"""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.core.enums import IntegrityStatus
from cii.database.database import Database
from cii.database.repositories import ProjectRepository, SymbolRepository
from cii.integrity.validator import Validator


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
    yield app
    database.close()


class TestDatabaseRecovery:
    def test_rebuild_from_source_recovers_lost_database(
        self, application
    ) -> None:
        """If the database is destroyed, re-init + scan rebuilds the index
        from source files (PLAN.md §18.2)."""
        root = application.project_root
        _write(root / "a.py", "class A:\n    def m(self):\n        pass\n")
        _write(root / "b.cpp", "class B { public: void go(); };\n")
        application.scan()
        application.close()

        db_path = root / ".cii" / "cii.db"
        db_path.unlink()  # database destroyed
        (root / ".cii" / "CODEBASE_INDEX.md").unlink()

        database = Database.open(root)  # re-created empty (as after `cii init`)
        ProjectRepository(database.connection).register(
            "demo", str(root), "1.0", "hash"
        )
        app = Application(root, CiiConfig.defaults(), database)
        try:
            outcome = app.scan()
            assert outcome.index.files_indexed == 2
            symbols = SymbolRepository(database.connection)
            assert symbols.list_by_name("A")
            assert symbols.list_by_name("B")
        finally:
            database.close()

    def test_corrupt_database_reported_not_silently_recreated(
        self, application
    ) -> None:
        from cii.core.exceptions import CiiError

        root = application.project_root
        application.scan()
        application.close()
        db_path = root / ".cii" / "cii.db"
        db_path.write_bytes(b"this is not a sqlite database at all")

        # opening must surface the corruption as a clear CII error —
        # never crash with a raw driver error, never silently wipe data
        with pytest.raises(CiiError, match="database"):
            Database.open(root)

    def test_backup_precedes_migrations(self, application) -> None:
        from cii.database.migrations import backup_database

        root = application.project_root
        application.scan()
        backup = backup_database(application.database.path,
                                 application.database.schema_version())
        assert backup.is_file()
        assert backup.parent == root / ".cii"


class TestParserFailureRecovery:
    def test_break_then_fix_recovers_automatically(self, application) -> None:
        root = application.project_root
        path = root / "mod.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()

        _write(path, "class Widget(:\n  !!broken\n")
        outcome = application.scan()
        assert outcome.index.files_failed == 1
        summary = Validator(root, application.config, application.database).validate()
        assert summary.status is IntegrityStatus.INCOMPLETE

        _write(path, "class Widget:\n    def render(self):\n        pass\n")
        outcome = application.scan()
        assert outcome.index.files_failed == 0
        assert outcome.index.symbols_added == 1  # the new method
        summary = Validator(root, application.config, application.database).validate()
        assert summary.status is IntegrityStatus.HEALTHY

    def test_failed_parse_never_deletes_previous_symbols(self, application) -> None:
        root = application.project_root
        path = root / "mod.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()
        before = SymbolRepository(application.database.connection).list_by_name("Widget")
        assert before

        _write(path, "def broken(:\n")
        application.scan()
        after = SymbolRepository(application.database.connection).list_by_name("Widget")
        assert [(s.symbol_name, s.symbol_id) for s in after] == [
            (s.symbol_name, s.symbol_id) for s in before
        ]


class TestSecurityBoundaries:
    def test_env_files_are_never_indexed_or_read(self, application) -> None:
        root = application.project_root
        _write(root / ".env", "SECRET_TOKEN=super-secret-value\n")
        _write(root / "ok.py", "x = 1\n")
        outcome = application.scan()
        indexed = [record.relative_path for record in outcome.scan.changes.added]
        assert indexed == ["ok.py"]  # .env has no parser mapping: never opened

    def test_files_outside_root_never_indexed(self, application, tmp_path) -> None:
        outside = tmp_path / "outside.py"
        _write(outside, "class Outside:\n    pass\n")
        outcome = application.scan()
        assert outcome.scan.changes.added == []

    def test_mcp_tools_do_not_modify_source_files(self, application) -> None:
        from cii.mcp import tools as tool_impl

        root = application.project_root
        _write(root / "a.py", "class A:\n    pass\n")
        before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        tool_impl.index_scan(application)
        tool_impl.index_validate(application, full_scan=True)
        tool_impl.index_rebuild(application, confirm=True)
        after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        source_before = {k: v for k, v in before.items() if not str(k).startswith(".cii")}
        source_after = {
            k: v for k, v in after.items()
            if not str(k).startswith(".cii") and k != Path(".cii")
        }
        assert source_before == source_after
