"""End-to-end indexer pipeline tests (PLAN.md §9.1, §8.4)."""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.core.enums import ScanStatus, SymbolType
from cii.database.repositories import (
    FileRepository,
    ProjectRepository,
    RelationshipRepository,
    SymbolRepository,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def application(project_root: Path):
    config = CiiConfig.defaults()
    from cii.database.database import Database

    database = Database.open(project_root)
    ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    yield Application(project_root, config, database)
    database.close()


class TestIndexing:
    def test_symbols_registered_with_parents(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    def render(self):\n        pass\n")
        _write(root / "util.cpp", "namespace ns { class C { public: void go(); }; }\n")
        outcome = application.scan()

        assert outcome.index.files_indexed == 2
        assert outcome.index.symbols_added >= 4
        repo = SymbolRepository(application.database.connection)
        rows = repo.list_by_name("render")
        assert len(rows) == 1
        assert rows[0].symbol_type == SymbolType.METHOD.value
        parents = repo.list_by_name("Widget")
        assert parents and rows[0].parent_symbol_id == parents[0].symbol_id

    def test_counts_reflect_extracted_symbols(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n")
        application.scan()
        from cii.database.repositories import FileRepository
        from cii.indexer.indexer import counts_for_file

        files = FileRepository(application.database.connection).list_all(
            ProjectRepository(application.database.connection)
            .get_by_root(str(root)).project_id
        )
        counts = counts_for_file(application.database, int(files[0].file_id))
        assert counts.classes == 1
        assert counts.methods == 1
        assert counts.functions == 1

    def test_cross_file_relationship_survives_target_reindex(self, application) -> None:
        root = application.project_root
        _write(root / "base.py", "class Base:\n    pass\n")
        _write(root / "child.py", "from base import Base\n\nclass Child(Base):\n    pass\n")
        outcome = application.scan()
        assert outcome.index.relationships_recorded >= 1

        # Reindex the BASE file (new method added) — the child -> base edge
        # must survive because the unchanged Base symbol keeps its id.
        _write(root / "base.py", "class Base:\n    def extra(self):\n        pass\n")
        application.scan()
        repo = RelationshipRepository(application.database.connection)
        symbol_repo = SymbolRepository(application.database.connection)
        child = symbol_repo.list_by_name("Child")[0]
        edges = repo.list_for_symbol(int(child.symbol_id), ["inherits"])
        assert len(edges) == 1
        assert edges[0].target_symbol_id == int(symbol_repo.list_by_name("Base")[0].symbol_id)

    def test_unresolved_references_are_counted_not_stored(self, application) -> None:
        root = application.project_root
        _write(root / "child.py", "class Child(UnknownBase):\n    pass\n")
        outcome = application.scan()
        assert outcome.index.relationships_unresolved == 1
        assert outcome.index.relationships_recorded == 0

    def test_parse_failure_retains_previous_index(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        symbol_repo = SymbolRepository(application.database.connection)
        before = [(row.symbol_name, row.symbol_id) for row in symbol_repo.list_by_name("Widget")]
        assert before

        _write(root / "mod.py", "class Widget(:\n  broken syntax !!\n")
        outcome = application.scan()
        assert outcome.index.files_failed == 1
        failed = outcome.index.outcomes[0]
        assert failed.status == "failed"
        assert failed.retained_previous_index is True
        after = [(row.symbol_name, row.symbol_id) for row in symbol_repo.list_by_name("Widget")]
        assert after == before  # previous valid index untouched

        files = FileRepository(application.database.connection).list_all(
            ProjectRepository(application.database.connection)
            .get_by_root(str(root)).project_id
        )
        assert files[0].scan_status == ScanStatus.FAILED.value

    def test_deleted_file_removes_symbols(self, application) -> None:
        root = application.project_root
        path = root / "mod.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()
        path.unlink()
        outcome = application.scan()
        assert outcome.scan.changes.deleted == ["mod.py"]
        symbol_repo = SymbolRepository(application.database.connection)
        assert symbol_repo.list_by_name("Widget") == []

    def test_incremental_reindex_only_changed_files(self, application) -> None:
        root = application.project_root
        _write(root / "a.py", "class A:\n    pass\n")
        _write(root / "b.py", "class B:\n    pass\n")
        application.scan()
        _write(root / "a.py", "class A:\n    def m(self):\n        pass\n")
        outcome = application.scan()
        assert outcome.scan.changes.modified == [
            record for record in outcome.scan.changes.modified
            if record.relative_path == "a.py"
        ]
        indexed_paths = [o.relative_path for o in outcome.index.outcomes]
        assert indexed_paths == ["a.py"]

    def test_renamed_file_keeps_symbols(self, application) -> None:
        root = application.project_root
        path = root / "old.py"
        _write(path, "class Widget:\n    pass\n")
        application.scan()
        symbol_repo = SymbolRepository(application.database.connection)
        before_id = int(symbol_repo.list_by_name("Widget")[0].symbol_id)
        path.rename(root / "new.py")
        application.scan()
        row = symbol_repo.list_by_name("Widget")[0]
        assert int(row.symbol_id) == before_id
