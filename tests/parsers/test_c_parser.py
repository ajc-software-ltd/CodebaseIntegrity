"""C parser tests against the representative fixture (PLAN.md §20.2)."""

from pathlib import Path

from _parser_helpers import find_symbol

from cii.core.enums import Language, SymbolType
from cii.parsers.cpp.parser import CFamilyParser

PARSER = CFamilyParser(Language.C)


class TestCExtraction:
    def test_result_metadata(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        assert result.ok is True
        assert result.language == Language.C
        assert result.parser_name == "tree-sitter-c"
        assert result.issues == []

    def test_structs_unions_enums(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        assert find_symbol(result.symbols, "AudioDevice", SymbolType.STRUCT) is not None
        assert find_symbol(result.symbols, "Wave", SymbolType.STRUCT) is not None
        assert find_symbol(result.symbols, "Value", SymbolType.UNION) is not None
        assert find_symbol(result.symbols, "Channel", SymbolType.ENUM) is not None

    def test_typedefs(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        typedefs = [
            symbol for symbol in result.symbols
            if symbol.symbol_type is SymbolType.TYPEDEF
        ]
        names = sorted(symbol.name for symbol in typedefs)
        assert names == ["AudioConfig", "AudioDevice"]

    def test_anonymous_struct_not_symbolised(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        # typedef struct { ... } AudioConfig — anonymous struct contributes
        # only the typedef symbol
        structs = [
            symbol.fully_qualified_name for symbol in result.symbols
            if symbol.symbol_type is SymbolType.STRUCT
        ]
        assert "AudioConfig" not in structs

    def test_functions_and_overloads(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        overloads = [
            symbol for symbol in result.symbols
            if symbol.fully_qualified_name == "audio_init"
        ]
        assert len(overloads) == 2
        assert find_symbol(result.symbols, "audio_start", SymbolType.FUNCTION) is not None
        assert find_symbol(result.symbols, "audio_stop", SymbolType.FUNCTION) is not None

    def test_no_namespaces_in_c(self, fixtures_dir: Path) -> None:
        result = PARSER.parse(fixtures_dir / "c_sample.c", "c_sample.c")
        assert result.namespaces == []
        assert result.references == []
