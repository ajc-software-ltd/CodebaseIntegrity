"""Markdown index export tests (PLAN.md §14)."""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.database.database import Database
from cii.database.repositories import ProjectRepository


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
    yield Application(project_root, config, database)
    database.close()


class TestExport:
    def test_generates_complete_index(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", (
            "class Widget:\n"
            "    def render(self):\n"
            "        return 'body content must not be exported'\n"
            "\n"
            "def helper():\n"
            "    pass\n"
        ))
        application.scan()
        index_path = root / ".cii" / "CODEBASE_INDEX.md"
        assert index_path.is_file()
        content = index_path.read_text()

        assert "PROJECT: demo" in content
        assert "INDEX_VERSION: 1.0" in content
        assert "FILE: mod.py" in content
        assert "LANGUAGE: Python" in content
        assert "[COUNTS]" in content
        assert "Classes: 1" in content
        assert "Functions: 1" in content
        assert "[CLASSES]" in content
        assert "Widget" in content
        assert "[METHODS]" in content
        assert "Widget:" in content
        assert "    render" in content
        assert "LAST_SCANNED:" in content
        # no source bodies
        assert "body content must not be exported" not in content

    def test_deterministic_and_skips_unchanged(self, application) -> None:
        root = application.project_root
        _write(root / "mod.py", "class Widget:\n    pass\n")
        application.scan()
        index_path = root / ".cii" / "CODEBASE_INDEX.md"
        first = index_path.read_text()
        written = application.export()
        assert written == []  # unchanged content is not rewritten
        assert index_path.read_text() == first

    def test_cpp_structure_rendered(self, application) -> None:
        root = application.project_root
        _write(root / "v.cpp", (
            "namespace ns {\n"
            "class C {\n"
            "public:\n"
            "    void go();\n"
            "};\n"
            "}\n"
        ))
        application.scan()
        content = (root / ".cii" / "CODEBASE_INDEX.md").read_text()
        assert "LANGUAGE: C++" in content
        assert "[NAMESPACES]" in content
        assert "ns" in content
        assert "ns::C" in content

    def test_split_by_language(self, project_root: Path) -> None:
        config = CiiConfig.defaults()
        config.output.split_by_language = True
        database = Database.open(project_root)
        ProjectRepository(database.connection).register(
            "demo", str(project_root), "1.0", "hash"
        )
        application = Application(project_root, config, database)
        try:
            _write(project_root / "mod.py", "class Widget:\n    pass\n")
            _write(project_root / "v.cpp", "class C { void go(); };\n")
            application.scan()
            assert (project_root / ".cii" / "indexes" / "python.md").is_file()
            assert (project_root / ".cii" / "indexes" / "cpp.md").is_file()
            assert "LANGUAGE: Python" in (
                project_root / ".cii" / "indexes" / "python.md"
            ).read_text()
        finally:
            database.close()
