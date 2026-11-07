"""Extraction tests for the extended language set (PLAN.md §8.3)."""

from pathlib import Path

from _parser_helpers import find_symbol

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.parsers.cpp.parser import CFamilyParser
from cii.parsers.treesitter.generic import SpecParser
from cii.parsers.treesitter.specs import NEW_LANGUAGE_SPECS

SPECS = {spec.language: SpecParser(spec) for spec in NEW_LANGUAGE_SPECS}


_BY_FILE = {
    "js_sample.js": Language.JAVASCRIPT,
    "ts_sample.ts": Language.TYPESCRIPT,
    "rust_sample.rs": Language.RUST,
    "java_sample.java": Language.JAVA,
    "go_sample.go": Language.GO,
    "lua_sample.lua": Language.LUA,
    "cmake_sample.cmake": Language.CMAKE,
    "glsl_sample.glsl": Language.GLSL,
    "hlsl_sample.hlsl": Language.HLSL,
}


def _parse(fixtures_dir: Path, filename: str):
    language = _BY_FILE[filename]
    parser = SPECS.get(language) or CFamilyParser(language)
    return parser.parse(fixtures_dir / filename, filename)


class TestJavaScript:
    def test_classes_methods_functions(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "js_sample.js")
        assert result.ok
        engine = find_symbol(result.symbols, "Engine", SymbolType.CLASS)
        assert engine is not None
        ctor = find_symbol(result.symbols, "Engine.constructor", SymbolType.CONSTRUCTOR)
        assert ctor is not None and ctor.parent == "Engine"
        start = find_symbol(result.symbols, "Engine.start", SymbolType.METHOD)
        assert start is not None and start.parent == "Engine"
        assert find_symbol(result.symbols, "Engine.create", SymbolType.METHOD) is not None
        assert find_symbol(result.symbols, "bootstrap", SymbolType.FUNCTION) is not None
        inner = find_symbol(result.symbols, "bootstrap.logStep", SymbolType.FUNCTION)
        assert inner is not None and inner.parent == "bootstrap"

    def test_inheritance(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "js_sample.js")
        assert any(r.source_fqn == "Engine" and r.target_name == "BaseEngine"
                   and r.relationship_type is RelationshipType.INHERITS
                   for r in result.references)

    def test_arrow_constants_not_extracted(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "js_sample.js")
        assert find_symbol(result.symbols, "helper") is None


class TestTypeScript:
    def test_namespaces_types_functions(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "ts_sample.ts")
        assert [(n.namespace_name, n.parent_name) for n in result.namespaces] == [
            ("App", None), ("App.Services", "App"),
        ]
        assert find_symbol(result.symbols, "App.Services.IRenderer",
                           SymbolType.INTERFACE) is not None
        assert find_symbol(result.symbols, "App.Services.Renderer",
                           SymbolType.CLASS) is not None
        assert find_symbol(result.symbols, "App.Services.Mode", SymbolType.ENUM) is not None
        assert find_symbol(result.symbols, "App.Services.Callback",
                           SymbolType.TYPEDEF) is not None
        assert find_symbol(result.symbols, "App.Services.configure",
                           SymbolType.FUNCTION) is not None

    def test_members_and_interface_signatures(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "ts_sample.ts")
        render = find_symbol(result.symbols, "App.Services.IRenderer.render",
                             SymbolType.METHOD)
        assert render is not None
        assert find_symbol(result.symbols, "App.Services.Renderer.render",
                           SymbolType.METHOD) is not None
        assert find_symbol(result.symbols, "App.Services.Renderer.constructor",
                           SymbolType.CONSTRUCTOR) is not None

    def test_heritage(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "ts_sample.ts")
        pairs = {(r.source_fqn.split(".")[-1], r.target_name, r.relationship_type)
                 for r in result.references}
        assert ("Renderer", "IRenderer", RelationshipType.IMPLEMENTS) in pairs
        assert ("IRenderer", "IBase", RelationshipType.INHERITS) in pairs


class TestRust:
    def test_modules_structs_traits_enums(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "rust_sample.rs")
        assert [(n.namespace_name, n.parent_name) for n in result.namespaces] == [
            ("render", None),
        ]
        renderer = find_symbol(result.symbols, "render::Renderer", SymbolType.STRUCT)
        assert renderer is not None
        assert renderer.visibility is Visibility.PUBLIC
        assert find_symbol(result.symbols, "render::Drawable",
                           SymbolType.INTERFACE) is not None
        assert find_symbol(result.symbols, "render::Mode", SymbolType.ENUM) is not None
        assert find_symbol(result.symbols, "render::helper",
                           SymbolType.FUNCTION) is not None

    def test_impl_and_trait_methods(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "rust_sample.rs")
        new = find_symbol(result.symbols, "render::Renderer::new", SymbolType.METHOD)
        assert new is not None and new.parent == "render::Renderer"
        resize = find_symbol(result.symbols, "render::Renderer::resize",
                             SymbolType.METHOD)
        assert resize is not None
        draw = find_symbol(result.symbols, "render::Drawable::draw", SymbolType.METHOD)
        assert draw is not None and draw.parent == "render::Drawable"

    def test_impl_for_trait_evidence(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "rust_sample.rs")
        assert any(r.target_name == "Drawable"
                   and r.relationship_type is RelationshipType.IMPLEMENTS
                   for r in result.references)

    def test_default_visibility_is_private(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "rust_sample.rs")
        draw = find_symbol(result.symbols, "render::Drawable::draw", SymbolType.METHOD)
        assert draw is not None and draw.visibility is Visibility.PRIVATE


class TestJava:
    def test_packages_types_members(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "java_sample.java")
        assert [n.namespace_name for n in result.namespaces] == [
            "com", "com.example", "com.example.render",
        ]
        renderer = find_symbol(result.symbols, "com.example.render.Renderer",
                               SymbolType.CLASS)
        assert renderer is not None and renderer.visibility is Visibility.PUBLIC
        ctor = find_symbol(result.symbols, "com.example.render.Renderer.Renderer",
                           SymbolType.CONSTRUCTOR)
        assert ctor is not None
        render = find_symbol(result.symbols, "com.example.render.Renderer.render",
                             SymbolType.METHOD)
        assert render is not None and render.visibility is Visibility.PUBLIC
        scope = find_symbol(result.symbols, "com.example.render.Renderer.Scope",
                            SymbolType.CLASS)
        assert scope is not None and scope.parent == "com.example.render.Renderer"

    def test_interfaces_and_defaults(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "java_sample.java")
        iface = find_symbol(result.symbols, "com.example.render.IRenderer",
                            SymbolType.INTERFACE)
        assert iface is not None and iface.visibility is Visibility.INTERNAL
        count_field_ok = all(s.name != "count" for s in result.symbols)
        assert count_field_ok

    def test_heritage(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "java_sample.java")
        pairs = {(r.target_name, r.relationship_type) for r in result.references}
        assert ("Base", RelationshipType.INHERITS) in pairs
        assert ("IRenderer", RelationshipType.IMPLEMENTS) in pairs


class TestGo:
    def test_packages_types_functions(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "go_sample.go")
        assert [n.namespace_name for n in result.namespaces] == ["render"]
        renderer = find_symbol(result.symbols, "render.Renderer", SymbolType.STRUCT)
        assert renderer is not None
        assert find_symbol(result.symbols, "render.Drawable",
                           SymbolType.INTERFACE) is not None
        new = find_symbol(result.symbols, "render.New", SymbolType.FUNCTION)
        assert new is not None and new.parent is None

    def test_receiver_methods(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "go_sample.go")
        draw = find_symbol(result.symbols, "render.Renderer.Draw", SymbolType.METHOD)
        assert draw is not None and draw.parent == "render.Renderer"
        resize = find_symbol(result.symbols, "render.Renderer.Resize",
                             SymbolType.METHOD)
        assert resize is not None

    def test_export_visibility(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "go_sample.go")
        assert find_symbol(result.symbols, "render.New").visibility is Visibility.PUBLIC
        draw = find_symbol(result.symbols, "render.Renderer.Draw", SymbolType.METHOD)
        assert draw.visibility is Visibility.PUBLIC  # exported: upper-case name


class TestLua:
    def test_functions_and_methods(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "lua_sample.lua")
        start = find_symbol(result.symbols, "M.start", SymbolType.METHOD)
        assert start is not None and start.parent == "M"
        stop = find_symbol(result.symbols, "M.stop", SymbolType.METHOD)
        assert stop is not None and stop.parent == "M"
        assert find_symbol(result.symbols, "helper", SymbolType.FUNCTION) is not None
        assert find_symbol(result.symbols, "global_setup",
                           SymbolType.FUNCTION) is not None

    def test_nested_functions(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "lua_sample.lua")
        inner = find_symbol(result.symbols, "helper.inner", SymbolType.FUNCTION)
        assert inner is not None and inner.parent == "helper"


class TestCMake:
    def test_functions_and_macros(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "cmake_sample.cmake")
        assert result.ok
        assert find_symbol(result.symbols, "my_add_library",
                           SymbolType.FUNCTION) is not None
        assert find_symbol(result.symbols, "my_init", SymbolType.FUNCTION) is not None


class TestShaders:
    def test_glsl(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "glsl_sample.glsl")
        assert result.ok
        assert find_symbol(result.symbols, "Light", SymbolType.STRUCT) is not None
        assert find_symbol(result.symbols, "shade", SymbolType.FUNCTION) is not None

    def test_hlsl(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir, "hlsl_sample.hlsl")
        assert result.ok
        assert find_symbol(result.symbols, "VS_INPUT", SymbolType.STRUCT) is not None
        assert find_symbol(result.symbols, "main", SymbolType.FUNCTION) is not None
