"""Search and retrieval tests (PLAN.md §11)."""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.database.database import Database
from cii.database.repositories import ProjectRepository
from cii.search.file_search import search_files
from cii.search.relationship_search import search_relationships
from cii.search.symbol_search import file_structure, search_namespaces, search_symbols


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def application(project_root: Path):
    config = CiiConfig.defaults()
    database = Database.open(project_root)
    project = ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    application = Application(project_root, config, database)
    yield application, project.project_id
    database.close()


@pytest.fixture
def indexed(application):
    app, project_id = application
    root = app.project_root
    _write(root / "renderer.cpp", (
        "namespace render {\n"
        "class VulkanRenderer {\n"
        "public:\n"
        "    void initialize();\n"
        "    void shutdown();\n"
        "};\n"
        "}\n"
    ))
    _write(root / "audio.cpp", (
        "namespace audio {\n"
        "class AudioEngine {\n"
        "public:\n"
        "    void initialize();\n"
        "};\n"
        "}\n"
    ))
    _write(root / "base.py", "class Base:\n    pass\n")
    _write(root / "child.py", "class Child(Base):\n    def render(self):\n        pass\n")
    app.scan()
    return app, project_id


class TestSymbolSearch:
    def test_finds_all_implementations(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "initialize")
        assert page.total == 2
        names = {hit.fully_qualified_name for hit in page.results}
        assert names == {"render::VulkanRenderer::initialize",
                         "audio::AudioEngine::initialize"}

    def test_exact_name_ranks_first(self, indexed) -> None:
        app, project_id = indexed
        _write(app.project_root / "x.cpp", "void initialize_helper() {}\n")
        app.scan()
        page = search_symbols(app.database, project_id, "initialize")
        assert page.results[0].name == "initialize"

    def test_type_filter(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "initialize", symbol_type="method")
        assert page.total == 2
        page = search_symbols(app.database, project_id, "initialize", symbol_type="class")
        assert page.total == 0

    def test_language_filter(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "render", language="python")
        assert {hit.name for hit in page.results} == {"render"}

    def test_pagination(self, indexed) -> None:
        app, project_id = indexed
        first = search_symbols(app.database, project_id, "i", limit=1, offset=0)
        second = search_symbols(app.database, project_id, "i", limit=1, offset=1)
        assert first.total == second.total >= 2
        assert first.results[0].fully_qualified_name != second.results[0].fully_qualified_name

    def test_concise_by_default_expanded_on_request(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "initialize")
        concise = next(
            hit for hit in page.results
            if hit.fully_qualified_name == "render::VulkanRenderer::initialize"
        )
        assert concise.signature is None
        assert concise.start_line is None
        assert concise.parent == "VulkanRenderer"
        assert concise.namespace == "render"
        assert concise.file_status == "indexed"
        expanded = search_symbols(
            app.database, project_id, "initialize", expanded=True
        ).results[0]
        assert expanded.signature is not None
        assert expanded.start_line is not None
        assert expanded.last_scanned is not None

    def test_namespace_attribution(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "VulkanRenderer")
        assert page.results[0].namespace == "render"

    def test_empty_query_result(self, indexed) -> None:
        app, project_id = indexed
        page = search_symbols(app.database, project_id, "zzz_missing")
        assert page.total == 0
        assert page.results == []


class TestNamespaceSearch:
    def test_search_namespaces(self, indexed) -> None:
        app, project_id = indexed
        hits = search_namespaces(app.database, project_id, "ren")
        assert {hit.name for hit in hits} == {"render"}


class TestFileSearch:
    def test_search_by_filename(self, indexed) -> None:
        app, project_id = indexed
        page = search_files(app.database, project_id, "audio")
        assert [hit.relative_path for hit in page.results] == ["audio.cpp"]

    def test_search_by_path_fragment_and_language(self, indexed) -> None:
        app, project_id = indexed
        page = search_files(app.database, project_id, ".", language="python")
        assert {hit.relative_path for hit in page.results} == {"base.py", "child.py"}

    def test_pagination(self, indexed) -> None:
        app, project_id = indexed
        page = search_files(app.database, project_id, ".", limit=2, offset=0)
        assert page.total == 4
        assert len(page.results) == 2


class TestRelationshipSearch:
    def test_outgoing_inherits(self, indexed) -> None:
        app, project_id = indexed
        page = search_relationships(
            app.database, project_id, "Child", relationship_types=["inherits"]
        )
        assert page.total == 1
        hit = page.results[0]
        assert hit.direction == "outgoing"
        assert hit.source.name == "Child"
        assert hit.target.name == "Base"
        assert hit.target.file_path == "base.py"

    def test_incoming_relationships(self, indexed) -> None:
        app, project_id = indexed
        page = search_relationships(app.database, project_id, "Base")
        assert page.total >= 1
        assert any(hit.direction == "incoming" for hit in page.results)

    def test_unknown_symbol(self, indexed) -> None:
        app, project_id = indexed
        page = search_relationships(app.database, project_id, "Missing")
        assert page.total == 0


class TestFileStructure:
    def test_structure(self, indexed) -> None:
        app, project_id = indexed
        structure = file_structure(app.database, project_id, "renderer.cpp")
        assert structure is not None
        assert structure.language == "cpp"
        assert structure.namespaces == ["render"]
        assert structure.counts.classes == 1
        assert structure.counts.methods == 2
        methods = [s.name for s in structure.symbols if s.symbol_type == "method"]
        assert methods == ["initialize", "shutdown"]

    def test_unknown_file(self, indexed) -> None:
        app, project_id = indexed
        assert file_structure(app.database, project_id, "missing.cpp") is None
