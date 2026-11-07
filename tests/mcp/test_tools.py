"""MCP tool logic tests (PLAN.md §12.1, §12.3)."""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.core.exceptions import CiiError, PathSecurityError
from cii.database.database import Database
from cii.database.repositories import ProjectRepository
from cii.mcp import tools as tool_impl


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
    _write(project_root / "base.py", "class Base:\n    pass\n")
    _write(project_root / "child.py", "class Child(Base):\n    def render(self):\n        pass\n")
    app.scan()
    yield app
    database.close()


class TestIndexStatus:
    def test_status(self, application) -> None:
        status = tool_impl.index_status(application)
        assert status.project_name == "demo"
        assert status.indexed_file_count == 2
        assert status.indexed_symbol_count >= 3
        assert status.health == "healthy"
        assert status.failed_files == 0

    def test_incomplete_with_failed_parse(self, application) -> None:
        _write(application.project_root / "broken.py", "class Broken(:\n  !!\n")
        application.scan()
        status = tool_impl.index_status(application)
        assert status.health == "incomplete"
        assert status.failed_files == 1


class TestIndexSearch:
    def test_search(self, application) -> None:
        result = tool_impl.index_search(application, "render")
        assert result.total == 1
        assert result.results[0].name == "render"

    def test_filters(self, application) -> None:
        result = tool_impl.index_search(application, "render", symbol_type="class")
        assert result.total == 0


class TestIndexFile:
    def test_structure(self, application) -> None:
        structure = tool_impl.index_file(application, "child.py")
        assert structure.file_path == "child.py"
        assert [s.name for s in structure.symbols] == ["Child", "render"]

    def test_traversal_rejected(self, application) -> None:
        with pytest.raises(PathSecurityError):
            tool_impl.index_file(application, "../outside.py")

    def test_absolute_outside_root_rejected(self, application, tmp_path: Path) -> None:
        with pytest.raises(PathSecurityError):
            tool_impl.index_file(application, str(tmp_path / "outside.py"))

    def test_unindexed_file_reports_error(self, application) -> None:
        with pytest.raises(CiiError, match="not indexed"):
            tool_impl.index_file(application, "missing.py")


class TestIndexSymbol:
    def test_exact_name_lookup(self, application) -> None:
        result = tool_impl.index_symbol(application, "Child")
        assert result.total == 1
        assert result.results[0].fully_qualified_name == "Child"
        assert result.results[0].signature is not None

    def test_file_filter(self, application) -> None:
        result = tool_impl.index_symbol(application, "Child", file="base.py")
        assert result.total == 0
        result = tool_impl.index_symbol(application, "Child", file="child.py")
        assert result.total == 1


class TestIndexScan:
    def test_scan_all_changes(self, application) -> None:
        _write(application.project_root / "new.py", "class New:\n    pass\n")
        result = tool_impl.index_scan(application)
        assert result.status == "completed"
        assert result.added == 1
        assert result.files_indexed == 1

    def test_scan_with_path(self, application) -> None:
        _write(application.project_root / "new.py", "class New:\n    pass\n")
        result = tool_impl.index_scan(application, path="new.py")
        assert result.path == "new.py"
        assert result.added == 1

    def test_scan_path_traversal_rejected(self, application) -> None:
        with pytest.raises(PathSecurityError):
            tool_impl.index_scan(application, path="../outside.py")


class TestIndexRebuild:
    def test_requires_confirmation(self, application) -> None:
        with pytest.raises(CiiError, match="explicit confirmation"):
            tool_impl.index_rebuild(application, confirm=False)

    def test_rebuild_preserves_backup_and_reindexes(self, application) -> None:
        result = tool_impl.index_rebuild(application, confirm=True)
        assert result.status == "completed"
        assert Path(result.backup_path).is_file()
        assert result.files_indexed == 2
        assert result.symbols_indexed >= 3

    def test_failed_rebuild_keeps_previous_index(
        self, application, monkeypatch
    ) -> None:
        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated rebuild failure")

        monkeypatch.setattr("cii.scanner.scanner.time.time", boom)
        with pytest.raises(RuntimeError):
            tool_impl.index_rebuild(application, confirm=True)
        status = tool_impl.index_status(application)
        assert status.indexed_file_count == 2  # previous index intact


class TestIndexValidate:
    def test_validate(self, application) -> None:
        result = tool_impl.index_validate(application, full_scan=True)
        assert result.status in ("healthy", "warning")
        assert isinstance(result.findings, list)


class TestIndexDependencies:
    def test_dependencies(self, application) -> None:
        result = tool_impl.index_dependencies(
            application, "Child", relationship_types=["inherits"]
        )
        assert result.total == 1
        assert result.results[0].relationship_type == "inherits"
        assert result.results[0].target.name == "Base"

    def test_contains_edges_also_returned(self, application) -> None:
        result = tool_impl.index_dependencies(application, "Child")
        types = {hit.relationship_type for hit in result.results}
        assert types == {"contains", "inherits"}

    def test_type_filter(self, application) -> None:
        result = tool_impl.index_dependencies(
            application, "Child", relationship_types=["calls"]
        )
        assert result.total == 0


class TestIndexStatistics:
    def test_statistics(self, application) -> None:
        stats = tool_impl.index_statistics(application)
        assert stats.total_files == 2
        assert stats.files_by_language == {"python": 2}
        assert stats.total_symbols >= 3
        assert stats.parser_failures == 0
        assert stats.recent_scans  # scan history recorded
