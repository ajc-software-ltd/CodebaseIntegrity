"""End-to-end scanner tests against a real project tree and database."""

import os
from pathlib import Path

import pytest

from cii.core.configuration import CiiConfig
from cii.core.enums import SymbolType
from cii.core.exceptions import ProjectRootError
from cii.core.models import SymbolInfo
from cii.database.database import Database
from cii.database.repositories import (
    FileRepository,
    ProjectRepository,
    ScanHistoryRepository,
    SymbolRepository,
)
from cii.scanner.scanner import Scanner


def _write(path: Path, content: str = "x = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def scanner_setup(project_root: Path):
    config = CiiConfig.defaults()
    database = Database.open(project_root)
    project = ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    scanner = Scanner(project_root, config, database)
    yield project_root, project, scanner, database
    database.close()


class TestScan:
    def test_initial_scan_records_files(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        _write(project_root / "src" / "a.py")
        _write(project_root / "b.cpp", "int main() {}\n")
        result = scanner.scan()
        assert len(result.changes.added) == 2
        rows = FileRepository(database.connection).list_all(project.project_id)
        assert [row.relative_path for row in rows] == ["b.cpp", "src/a.py"]
        assert all(row.content_hash for row in rows)
        assert all(row.scan_status == "pending" for row in rows)

    def test_unmodified_file_unchanged_with_hash_skip(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        _write(project_root / "a.py")
        scanner.scan()
        result = scanner.scan()
        assert result.changes.unchanged_count == 1
        assert result.hash_skips == 1
        assert result.hashed_files == 0

    def test_same_content_new_mtime_still_unchanged_on_full(
        self, scanner_setup
    ) -> None:
        project_root, project, scanner, database = scanner_setup
        path = project_root / "a.py"
        _write(path)
        scanner.scan()
        os.utime(path, (1_000_000, 1_000_000))  # mtime changed, content identical
        result = scanner.scan(full=True)
        assert result.changes.unchanged_count == 1
        assert result.hashed_files == 1

    def test_tampered_timestamps_caught_by_full_scan(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        path = project_root / "a.py"
        _write(path)
        scanner.scan()
        stat = path.stat()
        path.write_text("x = 2\n")
        os.utime(path, (stat.st_atime, stat.st_mtime))  # same size + mtime
        incremental = scanner.scan()
        assert incremental.changes.unchanged_count == 1  # fast path trusts mtime
        full = scanner.scan(full=True)
        assert [r.relative_path for r in full.changes.modified] == ["a.py"]

    def test_modified_file_updates_row(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        path = project_root / "a.py"
        _write(path)
        scanner.scan()
        path.write_text("x = 2\n")
        result = scanner.scan()
        assert [r.relative_path for r in result.changes.modified] == ["a.py"]
        row = FileRepository(database.connection).get_by_path(project.project_id, "a.py")
        assert row.content_hash == result.changes.modified[0].content_hash

    def test_deleted_file_removed(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        path = project_root / "a.py"
        _write(path)
        scanner.scan()
        path.unlink()
        result = scanner.scan()
        assert result.changes.deleted == ["a.py"]
        assert FileRepository(database.connection).list_all(project.project_id) == []

    def test_rename_preserves_file_id_and_symbols(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        path = project_root / "a.py"
        _write(path)
        scanner.scan()
        row = FileRepository(database.connection).get_by_path(project.project_id, "a.py")
        SymbolRepository(database.connection).replace_for_file(
            int(row.file_id),
            [SymbolInfo(
                name="Widget",
                fully_qualified_name="Widget",
                symbol_type=SymbolType.CLASS,
                language="python",  # type: ignore[arg-type]
                file_path="a.py",
            )],
        )
        path.rename(project_root / "b.py")
        result = scanner.scan()
        assert len(result.changes.renamed) == 1
        assert result.changes.renamed[0].old_relative_path == "a.py"
        assert result.changes.renamed[0].new_relative_path == "b.py"
        new_row = FileRepository(database.connection).get_by_path(project.project_id, "b.py")
        assert new_row.file_id == row.file_id
        symbols = SymbolRepository(database.connection).list_by_file(int(row.file_id))
        assert [s.symbol_name for s in symbols] == ["Widget"]

    def test_scan_history_recorded(self, scanner_setup) -> None:
        project_root, project, scanner, database = scanner_setup
        _write(project_root / "a.py")
        result = scanner.scan()
        history = ScanHistoryRepository(database.connection).list_recent(project.project_id)
        assert len(history) == 1
        assert history[0].scan_id == result.scan_id
        assert history[0].status == "completed"
        assert history[0].scan_type == "incremental"
        full = scanner.scan(full=True)
        history = ScanHistoryRepository(database.connection).list_recent(project.project_id)
        assert history[0].scan_id == full.scan_id
        assert history[0].scan_type == "full"

    def test_unregistered_project_raises(self, project_root: Path) -> None:
        with Database.open(project_root) as database:
            scanner = Scanner(project_root, CiiConfig.defaults(), database)
            with pytest.raises(ProjectRootError, match="not registered"):
                scanner.scan()

    def test_failed_changes_leave_index_intact(self, scanner_setup, monkeypatch) -> None:
        project_root, project, scanner, database = scanner_setup
        _write(project_root / "a.py")
        scanner.scan()

        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated failure")

        monkeypatch.setattr("cii.scanner.scanner.time.time", boom)
        with pytest.raises(RuntimeError):
            scanner.scan()
        rows = FileRepository(database.connection).list_all(project.project_id)
        assert [row.relative_path for row in rows] == ["a.py"]
