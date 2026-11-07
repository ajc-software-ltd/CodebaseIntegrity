"""Python parser tests against the representative fixture (PLAN.md §20.2)."""

from pathlib import Path

from _parser_helpers import find_symbol

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.parsers.python.parser import PythonParser

PARSER = PythonParser()


def _parse(fixtures_dir: Path):
    return PARSER.parse(fixtures_dir / "python_sample.py", "python_sample.py")


class TestPythonExtraction:
    def test_result_metadata(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        assert result.ok is True
        assert result.language == Language.PYTHON
        assert result.parser_name == "python-ast"
        assert result.issues == []

    def test_classes_and_inheritance(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        engine = find_symbol(result.symbols, "Engine", SymbolType.CLASS)
        assert engine is not None
        assert engine.parent is None
        audio = find_symbol(result.symbols, "AudioEngine", SymbolType.CLASS)
        assert audio is not None
        assert audio.signature.startswith("class AudioEngine(Engine, Mixin)")
        inherits = {
            (reference.target_name, reference.relationship_type)
            for reference in result.references
            if reference.source_fqn == "AudioEngine"
        }
        assert inherits == {
            ("Engine", RelationshipType.INHERITS),
            ("Mixin", RelationshipType.INHERITS),
        }

    def test_module_scope_functions(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        health = find_symbol(result.symbols, "health_check", SymbolType.FUNCTION)
        assert health is not None
        assert "route" in health.signature  # decorator recorded in signature
        assert find_symbol(result.symbols, "outer", SymbolType.FUNCTION) is not None

    def test_methods_constructors_destructors(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        ctor = find_symbol(result.symbols, "Engine.__init__", SymbolType.CONSTRUCTOR)
        assert ctor is not None
        assert ctor.parent == "Engine"
        assert find_symbol(result.symbols, "Engine.__del__", SymbolType.DESTRUCTOR) is not None
        start = find_symbol(result.symbols, "AudioEngine.start", SymbolType.METHOD)
        assert start is not None
        assert "async def start(self)" in start.signature

    def test_properties_and_decorated_methods(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        prop = find_symbol(result.symbols, "Engine.status", SymbolType.PROPERTY)
        assert prop is not None
        assert "@property" in prop.signature
        setter = find_symbol(result.symbols, "Engine.status", SymbolType.METHOD)
        assert setter is not None
        assert "@status.setter" in setter.signature
        create = find_symbol(result.symbols, "Engine.create", SymbolType.METHOD)
        assert create is not None
        assert "@staticmethod" in create.signature

    def test_nested_functions_and_classes(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        nested = find_symbol(result.symbols, "outer.nested", SymbolType.FUNCTION)
        assert nested is not None
        assert nested.parent == "outer"
        device = find_symbol(result.symbols, "AudioEngine.Device", SymbolType.CLASS)
        assert device is not None
        assert device.parent == "AudioEngine"
        inner = find_symbol(result.symbols, "AudioEngine.Device.open.inner",
                            SymbolType.FUNCTION)
        assert inner is not None
        assert inner.parent == "AudioEngine.Device.open"

    def test_no_module_symbol_is_fabricated(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        assert all(symbol.symbol_type is not SymbolType.MODULE for symbol in result.symbols)

    def test_visibility_unknown_by_design(self, fixtures_dir: Path) -> None:
        result = _parse(fixtures_dir)
        assert all(symbol.visibility is Visibility.UNKNOWN for symbol in result.symbols)


class TestPythonFailures:
    def test_syntax_error_reported(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "invalid.py", "invalid.py")
        assert result.ok is False
        assert result.symbols == []
        assert result.issues
        assert "syntax error" in result.issues[0].reason

    def test_unreadable_file(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "missing.py", "missing.py")
        assert result.ok is False
        assert "read failed" in result.issues[0].reason

    def test_fingerprints_deterministic(self, fixtures_dir: Path) -> None:
        first = _parse(fixtures_dir)
        second = _parse(fixtures_dir)
        assert [s.fingerprint for s in first.symbols] == [s.fingerprint for s in second.symbols]
