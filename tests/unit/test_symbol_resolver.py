"""Tests for relationship target resolution."""

from cii.database.models import SymbolRow
from cii.indexer.symbol_resolver import normalise_target_name, resolve_target


def _row(name: str, fqn: str, symbol_id: int = 1) -> SymbolRow:
    return SymbolRow(
        symbol_id=symbol_id,
        file_id=1,
        symbol_name=name,
        fully_qualified_name=fqn,
        symbol_type="class",
    )


class TestNormalise:
    def test_strips_template_arguments(self) -> None:
        assert normalise_target_name("Base<T>") == "Base"
        assert normalise_target_name("std::vector<int>") == "std::vector"

    def test_strips_decorations(self) -> None:
        assert normalise_target_name("Base*") == "Base"
        assert normalise_target_name("Base &") == "Base"


class TestResolveTarget:
    def test_exact_fqn(self) -> None:
        candidates = [_row("Base", "A::Base"), _row("Other", "B::Other", 2)]
        assert resolve_target("A::Base", candidates).symbol_id == 1

    def test_simple_name(self) -> None:
        candidates = [_row("Base", "A::Base")]
        assert resolve_target("Base", candidates).symbol_id == 1

    def test_template_name_resolves(self) -> None:
        candidates = [_row("Base", "A::Base")]
        assert resolve_target("Base<T>", candidates).symbol_id == 1

    def test_trailing_component(self) -> None:
        candidates = [_row("Base", "A::B::Base")]
        assert resolve_target("B::Base", candidates).symbol_id == 1

    def test_ambiguous_simple_name_unresolved(self) -> None:
        candidates = [_row("Base", "A::Base"), _row("Base", "B::Base", 2)]
        assert resolve_target("Base", candidates) is None

    def test_unknown_unresolved(self) -> None:
        assert resolve_target("Missing", [_row("Base", "Base")]) is None

    def test_empty_unresolved(self) -> None:
        assert resolve_target("", [_row("Base", "Base")]) is None
