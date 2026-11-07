"""Shared helpers for parser tests."""

from cii.core.enums import SymbolType
from cii.core.models import SymbolInfo


def symbols_by_type(symbols: list[SymbolInfo]) -> dict[SymbolType, list[str]]:
    grouped: dict[SymbolType, list[str]] = {}
    for symbol in symbols:
        grouped.setdefault(symbol.symbol_type, []).append(symbol.fully_qualified_name)
    return grouped


def find_symbol(symbols: list[SymbolInfo], fqn: str,
                symbol_type: SymbolType | None = None) -> SymbolInfo | None:
    for symbol in symbols:
        if symbol.fully_qualified_name == fqn and (
            symbol_type is None or symbol.symbol_type is symbol_type
        ):
            return symbol
    return None
