"""C++ parser tests against the representative fixture (PLAN.md §20.2)."""

from pathlib import Path

from _parser_helpers import find_symbol

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.parsers.cpp.parser import CFamilyParser

PARSER = CFamilyParser(Language.CPP)


def _parse(fixtures_dir: Path):
    return PARSER.parse(fixtures_dir / "cpp_sample.cpp", "cpp_sample.cpp")


class TestCppExtraction:
    def test_result_metadata(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        assert result.ok is True
        assert result.language == Language.CPP
        assert result.parser_name == "tree-sitter-cpp"
        assert result.issues == []

    def test_namespaces(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        declarations = [(n.namespace_name, n.parent_name) for n in result.namespaces]
        assert sorted(declarations) == [
            ("VulkanOne", None),
            ("VulkanOne::Rendering", "VulkanOne"),
        ]

    def test_compact_nested_namespace_declares_components(self, tmp_path: Path) -> None:
        source = tmp_path / "compact.cpp"
        source.write_text("namespace a::b { void f(); }\n")
        result = PARSER.parse(source, "compact.cpp")
        declarations = [(n.namespace_name, n.parent_name) for n in result.namespaces]
        assert sorted(declarations) == [("a", None), ("a::b", "a")]

    def test_types(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        renderer = find_symbol(result.symbols, "VulkanOne::Rendering::VulkanRenderer",
                               SymbolType.CLASS)
        assert renderer is not None
        assert renderer.namespace == "VulkanOne::Rendering"
        assert renderer.signature.startswith("class VulkanRenderer : public BaseRenderer")
        assert find_symbol(result.symbols, "VulkanOne::Rendering::VulkanDevice",
                           SymbolType.CLASS) is not None
        assert find_symbol(result.symbols, "VulkanOne::Rendering::RenderSettings",
                           SymbolType.STRUCT) is not None
        assert find_symbol(result.symbols, "VulkanOne::Rendering::RenderMode",
                           SymbolType.ENUM) is not None

    def test_methods_and_constructors(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        ctor = find_symbol(result.symbols, "VulkanOne::Rendering::VulkanRenderer::VulkanRenderer",
                           SymbolType.CONSTRUCTOR)
        assert ctor is not None
        dtor = find_symbol(result.symbols, "VulkanOne::Rendering::VulkanRenderer::~VulkanRenderer",
                           SymbolType.DESTRUCTOR)
        assert dtor is not None
        for method in ("initialize", "shutdown", "begin_frame", "end_frame"):
            found = find_symbol(
                result.symbols, f"VulkanOne::Rendering::VulkanRenderer::{method}",
                SymbolType.METHOD,
            )
            assert found is not None, method
            assert found.parent == "VulkanOne::Rendering::VulkanRenderer"
            assert found.visibility == Visibility.PUBLIC

    def test_overloads_are_distinct_symbols(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        present = [
            symbol for symbol in result.symbols
            if symbol.fully_qualified_name == "VulkanOne::Rendering::VulkanRenderer::present"
        ]
        assert len(present) == 2
        assert present[0].fingerprint != present[1].fingerprint

    def test_access_modifiers(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        helper = find_symbol(result.symbols, "VulkanOne::Rendering::VulkanRenderer::helper",
                             SymbolType.METHOD)
        assert helper is not None
        assert helper.visibility == Visibility.PRIVATE

    def test_fields_are_not_extracted(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        assert all(symbol.name != "frame_" for symbol in result.symbols)

    def test_free_functions_and_templates(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        clamp = find_symbol(result.symbols, "VulkanOne::Rendering::clamp_value",
                            SymbolType.FUNCTION)
        assert clamp is not None
        assert clamp.signature.startswith("template<")
        overloads = [
            symbol for symbol in result.symbols
            if symbol.fully_qualified_name == "VulkanOne::Rendering::free_function"
        ]
        assert len(overloads) == 2

    def test_inheritance_references(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        inherits = {
            (reference.target_name, reference.relationship_type)
            for reference in result.references
            if reference.source_fqn == "VulkanOne::Rendering::VulkanRenderer"
        }
        assert inherits == {
            ("BaseRenderer", RelationshipType.INHERITS),
            ("IFramed", RelationshipType.INHERITS),
        }

    def test_fingerprints_are_deterministic(self, fixtures_dir: Path) -> None:
        first = _parse(fixtures_dir)
        second = _parse(fixtures_dir)
        assert [s.fingerprint for s in first.symbols] == [s.fingerprint for s in second.symbols]


class TestCppFailures:
    def test_syntax_errors_are_reported_but_extracted(self, fixtures_dir: Path,
                                                      tmp_path: Path) -> None:
        broken = tmp_path / "broken.cpp"
        broken.write_text("class { void f( {}\nint good_function() { return 1; }\n")
        result = PARSER.parse(broken, "broken.cpp")
        assert result.ok is True  # tolerant parse
        assert result.issues and "syntax error" in result.issues[0].reason
        assert find_symbol(result.symbols, "good_function", SymbolType.FUNCTION) is not None

    def test_unreadable_file_fails_without_symbols(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "does_not_exist.cpp", "missing.cpp")
        assert result.ok is False
        assert result.symbols == []
        assert result.issues and "read/parse failed" in result.issues[0].reason

    def test_declaration_functions_are_extracted(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        # header-style declarations (no body) count as function symbols
        decl = find_symbol(result.symbols, "VulkanOne::Rendering::free_function",
                           SymbolType.FUNCTION)
        assert decl is not None
