"""Tests for the repository layer."""


import pytest

from cii.core.enums import Language, SymbolType
from cii.core.models import NamespaceInput, SymbolInfo
from cii.database.database import Database
from cii.database.models import FileRow
from cii.database.repositories import (
    FileRepository,
    IntegrityReportRepository,
    NamespaceRepository,
    ProjectRepository,
    RelationshipRepository,
    ScanHistoryRepository,
    SymbolRepository,
)


def _symbol(name: str, fqn: str, parent: str | None = None, **kwargs: object) -> SymbolInfo:
    fields: dict = {
        "name": name,
        "fully_qualified_name": fqn,
        "symbol_type": SymbolType.METHOD,
        "language": Language.CPP,
        "file_path": "src/a.cpp",
        "parent": parent,
    }
    fields.update(kwargs)
    return SymbolInfo(**fields)


@pytest.fixture
def project(database: Database):
    return ProjectRepository(database.connection).register(
        project_name="demo",
        project_root="/tmp/demo",
        index_version="1.0",
        configuration_hash="hash1",
    )


class TestProjectRepository:
    def test_register_and_get(self, database: Database) -> None:
        repo = ProjectRepository(database.connection)
        project = repo.register("demo", "/tmp/demo", "1.0", "hash1")
        assert project.project_id
        assert repo.get(project.project_id) == project
        assert repo.get_by_root("/tmp/demo") == project
        assert repo.get("missing") is None

    def test_reregistration_updates_in_place(self, database: Database) -> None:
        repo = ProjectRepository(database.connection)
        first = repo.register("demo", "/tmp/demo", "1.0", "hash1")
        second = repo.register("demo2", "/tmp/demo", "1.0", "hash2")
        assert second.project_id == first.project_id
        assert second.project_name == "demo2"
        assert second.configuration_hash == "hash2"
        assert len(repo.list_all()) == 1

    def test_set_last_scan(self, database: Database, project) -> None:
        repo = ProjectRepository(database.connection)
        repo.set_last_scan(project.project_id, when=123.0)
        assert repo.get(project.project_id).last_scan == 123.0  # type: ignore[union-attr]


class TestFileRepository:
    def _row(self, project_id: str, path: str = "src/a.cpp", **kwargs: object) -> FileRow:
        defaults: dict = {
            "filename": "a.cpp",
            "extension": ".cpp",
            "language": "cpp",
            "content_hash": "h1",
            "file_size": 10,
            "modified_at": 1.0,
            "last_scanned": 2.0,
            "scan_status": "indexed",
            "parser_version": "1",
        }
        defaults.update(kwargs)
        return FileRow(project_id=project_id, relative_path=path, **defaults)

    def test_upsert_inserts_and_updates(self, database: Database, project) -> None:
        repo = FileRepository(database.connection)
        inserted = repo.upsert(self._row(project.project_id))
        assert inserted.file_id is not None
        updated = repo.upsert(self._row(project.project_id, content_hash="h2"))
        assert updated.file_id == inserted.file_id
        assert updated.content_hash == "h2"
        assert len(repo.list_all(project.project_id)) == 1

    def test_get_by_path(self, database: Database, project) -> None:
        repo = FileRepository(database.connection)
        inserted = repo.upsert(self._row(project.project_id))
        assert repo.get_by_path(project.project_id, "src/a.cpp") == inserted
        assert repo.get_by_path(project.project_id, "src/missing.cpp") is None

    def test_delete(self, database: Database, project) -> None:
        repo = FileRepository(database.connection)
        repo.upsert(self._row(project.project_id))
        assert repo.delete(project.project_id, "src/a.cpp") is True
        assert repo.delete(project.project_id, "src/a.cpp") is False

    def test_find_by_content_hash(self, database: Database, project) -> None:
        repo = FileRepository(database.connection)
        repo.upsert(self._row(project.project_id))
        repo.upsert(self._row(project.project_id, path="src/b.cpp", filename="b.cpp"))
        repo.upsert(self._row(project.project_id, path="src/c.cpp", filename="c.cpp",
                              content_hash="other"))
        matches = repo.find_by_content_hash(project.project_id, "h1")
        assert [m.relative_path for m in matches] == ["src/a.cpp", "src/b.cpp"]

    def test_count_by_status(self, database: Database, project) -> None:
        repo = FileRepository(database.connection)
        repo.upsert(self._row(project.project_id))
        repo.upsert(self._row(project.project_id, path="src/b.cpp", filename="b.cpp",
                              scan_status="failed"))
        assert repo.count_by_status(project.project_id, "indexed") == 1
        assert repo.count_by_status(project.project_id, "failed") == 1


class TestSymbolRepository:
    def test_replace_for_file_resolves_parents(self, database: Database, project) -> None:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        repo = SymbolRepository(database.connection)
        count = repo.replace_for_file(
            file_row.file_id,  # type: ignore[arg-type]
            [
                _symbol("Renderer", "Renderer", symbol_type=SymbolType.CLASS),
                _symbol("init", "Renderer::init", parent="Renderer"),
            ],
        )
        assert count == 2
        rows = repo.list_by_file(file_row.file_id)  # type: ignore[arg-type]
        assert [r.symbol_name for r in rows] == ["Renderer", "init"]
        assert rows[1].parent_symbol_id == rows[0].symbol_id

    def test_replace_removes_previous_symbols(self, database: Database, project) -> None:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        repo = SymbolRepository(database.connection)
        repo.replace_for_file(file_row.file_id, [_symbol("one", "one")])  # type: ignore[arg-type]
        repo.replace_for_file(file_row.file_id, [_symbol("two", "two")])  # type: ignore[arg-type]
        rows = repo.list_by_file(file_row.file_id)  # type: ignore[arg-type]
        assert [r.symbol_name for r in rows] == ["two"]

    def test_lookup_by_name_and_fqn(self, database: Database, project) -> None:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        repo = SymbolRepository(database.connection)
        repo.replace_for_file(file_row.file_id, [  # type: ignore[arg-type]
            _symbol("init", "A::init", symbol_type=SymbolType.METHOD),
            _symbol("init", "B::init", symbol_type=SymbolType.METHOD),
        ])
        assert len(repo.list_by_name("init", project.project_id)) == 2
        assert len(repo.list_by_name("init")) == 2
        assert [r.fully_qualified_name for r in repo.list_by_fully_qualified_name(
            "A::init", project.project_id)] == ["A::init"]
        assert repo.count_for_project(project.project_id) == 2

    def test_file_delete_cascades_to_symbols(self, database: Database, project) -> None:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        symbols = SymbolRepository(database.connection)
        symbols.replace_for_file(file_row.file_id, [_symbol("one", "one")])  # type: ignore[arg-type]
        files.delete(project.project_id, "src/a.cpp")
        assert symbols.list_by_file(file_row.file_id) == []  # type: ignore[arg-type]


class TestNamespaceRepository:
    def test_replace_resolves_parents(self, database: Database, project) -> None:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        repo = NamespaceRepository(database.connection)
        count = repo.replace_for_file(file_row.file_id, [  # type: ignore[arg-type]
            NamespaceInput(namespace_name="Outer"),
            NamespaceInput(namespace_name="Inner", parent_name="Outer"),
        ])
        assert count == 2
        rows = repo.list_by_file(file_row.file_id)  # type: ignore[arg-type]
        assert [n.namespace_name for n in rows] == ["Outer", "Inner"]
        assert rows[1].parent_namespace_id == rows[0].namespace_id


class TestRelationshipRepository:
    def _symbols(self, database: Database, project) -> tuple[int, int]:
        files = FileRepository(database.connection)
        file_row = files.upsert(FileRow(
            project_id=project.project_id,
            relative_path="src/a.cpp",
            filename="a.cpp",
            extension=".cpp",
            language="cpp",
        ))
        symbols = SymbolRepository(database.connection)
        symbols.replace_for_file(file_row.file_id, [  # type: ignore[arg-type]
            _symbol("A", "A", symbol_type=SymbolType.CLASS),
            _symbol("B", "B", symbol_type=SymbolType.CLASS),
        ])
        rows = symbols.list_by_file(file_row.file_id)  # type: ignore[arg-type]
        return int(rows[0].symbol_id), int(rows[1].symbol_id)

    def test_add_and_query(self, database: Database, project) -> None:
        source_id, target_id = self._symbols(database, project)
        repo = RelationshipRepository(database.connection)
        row = repo.add(source_id, target_id, "inherits")
        assert row.relationship_id is not None
        assert len(repo.list_for_symbol(source_id)) == 1
        assert len(repo.list_for_symbol(target_id)) == 1
        assert repo.list_for_symbol(source_id, ["calls"]) == []

    def test_duplicate_add_returns_existing_row(self, database: Database, project) -> None:
        source_id, target_id = self._symbols(database, project)
        repo = RelationshipRepository(database.connection)
        first = repo.add(source_id, target_id, "inherits")
        second = repo.add(source_id, target_id, "inherits")
        assert first.relationship_id == second.relationship_id
        assert len(repo.list_for_symbol(source_id)) == 1


class TestScanHistoryRepository:
    def test_start_finish_cycle(self, database: Database, project) -> None:
        repo = ScanHistoryRepository(database.connection)
        scan = repo.start(project.project_id, "full")
        assert scan.status == "running"
        finished = repo.finish(
            scan.scan_id,  # type: ignore[arg-type]
            files_processed=5,
            files_failed=1,
            symbols_added=3,
            status="completed",
        )
        assert finished.status == "completed"
        assert finished.files_processed == 5
        recent = repo.list_recent(project.project_id)
        assert len(recent) == 1


class TestIntegrityReportRepository:
    def test_add_and_list(self, database: Database, project) -> None:
        repo = IntegrityReportRepository(database.connection)
        report = repo.add(
            project.project_id,
            "healthy",
            files_checked=4,
            errors_found=0,
            warnings_found=1,
        )
        assert report.report_id is not None
        recent = repo.list_recent(project.project_id)
        assert len(recent) == 1
        assert recent[0].warnings_found == 1
