"""Tests for per-file symbol counting."""

from cii.core.enums import SymbolType
from cii.indexer.symbol_extractor import compute_counts


class TestComputeCounts:
    def test_empty(self) -> None:
        assert compute_counts([]).total == 0

    def test_counting_rules(self) -> None:
        counts = compute_counts(
            [
                SymbolType.CLASS,
                SymbolType.RECORD,
                SymbolType.STRUCT,
                SymbolType.UNION,
                SymbolType.INTERFACE,
                SymbolType.ENUM,
                SymbolType.FUNCTION,
                SymbolType.METHOD,
                SymbolType.CONSTRUCTOR,
                SymbolType.DESTRUCTOR,
                SymbolType.PROPERTY,
                SymbolType.TYPEDEF,
            ],
            namespace_count=2,
        )
        assert counts.namespaces == 2
        assert counts.classes == 2  # class + record
        assert counts.structures == 2  # struct + union
        assert counts.interfaces == 1
        assert counts.enums == 1
        assert counts.functions == 1
        assert counts.methods == 3  # method + constructor + destructor
        assert counts.properties == 1

    def test_accepts_string_types(self) -> None:
        counts = compute_counts(["class", "function"], namespace_count=0)
        assert counts.classes == 1
        assert counts.functions == 1

    def test_uncounted_types_do_not_break_totals(self) -> None:
        counts = compute_counts([SymbolType.TYPEDEF, SymbolType.EVENT, SymbolType.DELEGATE])
        assert counts.total == 0
