"""End-to-end integrity validation tests (PLAN.md §10).

Validation must identify discrepancies between the filesystem and the
database without corrupting existing records.
"""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.core.enums import IntegrityStatus
from cii.database.database import Database
from cii.database.repositories import (
    FileRepository,
    ProjectRepository,
    SymbolRepository,
)
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
    application = Application(project_root, config, database)
    yield application
    database.close()


def _validate(application, full_scan: bool = False):
    return Validator(
        application.project_root, application.config, application.database
    ).validate(full_scan=full_scan)


def _snapshot(application) -> list[tuple]:
    files = FileRepository(application.database.connection).list_all(
        ProjectRepository(application.database.connection)
        .get_by_root(str(application.project_root)).project_id
    )
    symbols = SymbolRepository(application.database.connection)
    return [
        (file_row.relative_path, file_row.content_hash, file_row.scan_status,
         [(s.symbol_name, s.symbol_id) for s in symbols.list_by_file(int(file_row.file_id))])
        for file_row in files
    ]


class TestValidation:
    def test_healthy_project(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        summary = _validate(application)
        assert summary.status is IntegrityStatus.HEALTHY
        assert summary.findings == []
        assert summary.errors == 0

    def test_unindexed_file_detected(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        _write(root / "new.py", "class New:\n    pass\n")
        summary = _validate(application)
        assert summary.status is IntegrityStatus.STALE
        assert [f.code for f in summary.findings] == ["unindexed_file"]
        assert summary.findings[0].file_path == "new.py"

    def test_missing_file_detected(self, application) -> None:
        root = application.project_root
        path = root / "mod.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()
        path.unlink()
        summary = _validate(application)
        assert summary.status is IntegrityStatus.STALE
        assert [f.code for f in summary.findings] == ["missing_file"]

    def test_changed_hash_detected(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        _write(root / "mod.py", "class Widget:\n    def m(self):\n        pass\n")
        summary = _validate(application)
        assert summary.status is IntegrityStatus.STALE
        assert [f.code for f in summary.findings] == ["changed_hash"]

    def test_rename_detected_without_loosing_symbols(self, application) -> None:
        root = application.project_root
        path = root / "old.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()
        path.rename(root / "new.py")
        summary = _validate(application)
        assert [f.code for f in summary.findings] == ["renamed_file"]
        assert summary.findings[0].file_path == "new.py"

    def test_parser_failure_reports_incomplete(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget(:\n  !!broken\n")
        application.scan()
        summary = _validate(application)
        assert summary.status is IntegrityStatus.INCOMPLETE
        assert [f.code for f in summary.findings] == ["parser_failure"]

    def test_duplicate_declarations_report_error(self, application) -> None:
        root = application.project_root
        _write(root / "a.cpp", "void f() {}\n")
        _write(root / "b.cpp", "void f() {}\n")
        application.scan()
        summary = _validate(application)
        assert summary.status is IntegrityStatus.ERROR
        duplicates = [f for f in summary.findings if f.code == "duplicate_declaration"]
        assert len(duplicates) == 1
        assert duplicates[0].file_path in ("a.cpp", "b.cpp")

    def test_header_source_pair_not_flagged(self, application) -> None:
        root = application.project_root
        _write(root / "a.h", "void f();\n")
        _write(root / "a.cpp", "void f() {}\n")
        application.scan()
        summary = _validate(application)
        assert not [f for f in summary.findings if f.code == "duplicate_declaration"]

    def test_validation_does_not_modify_records(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        _write(root / "mod.py", "class Widget:\n    def m(self):\n        pass\n")
        _write(root / "extra.py", "class Extra:\n    pass\n")
        before = _snapshot(application)
        _validate(application, full_scan=True)
        assert _snapshot(application) == before

    def test_report_rows_are_persisted(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        _validate(application)
        from cii.database.repositories import IntegrityReportRepository

        reports = IntegrityReportRepository(application.database.connection).list_recent(
            ProjectRepository(application.database.connection)
            .get_by_root(str(root)).project_id
        )
        assert len(reports) == 1
        assert reports[0].report_status == "healthy"

    def test_stale_markdown_detected(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        (root / ".cii" / "CODEBASE_INDEX.md").write_text("tampered\n")
        summary = _validate(application)
        assert [f.code for f in summary.findings] == ["stale_markdown"]

    def test_full_scan_detects_symbol_drift(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n\nclass Ghost:\n    pass\n")
        application.scan()
        # simulate drift: remove Ghost's row directly from the database
        connection = application.database.connection
        connection.execute("DELETE FROM symbols WHERE symbol_name = 'Ghost'")
        summary = _validate(application, full_scan=True)
        codes = {f.code for f in summary.findings}
        assert "new_symbols" in codes  # Ghost exists in source but not the index
        drift = [f for f in summary.findings if f.code == "new_symbols"]
        assert drift[0].symbol == "Ghost"

    def test_full_scan_reports_unresolved_relationships(self, application) -> None:
        root = application.project_root
        _write(root / "child.py", "class Child(UnknownBase):\n    pass\n")
        application.scan()
        summary = _validate(application, full_scan=True)
        assert any(f.code == "unresolved_relationship" for f in summary.findings)
