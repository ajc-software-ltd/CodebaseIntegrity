"""Per-file symbol counting.

Counts are always derived from extracted symbols (PLAN.md §5.2) — never
inferred or entered manually. Counting rules:

- classes   = class + record declarations
- structures= struct + union declarations
- methods   = methods + constructors + destructors
- functions = free functions (incl. nested functions)
- namespaces= namespace declarations of the file
- properties, interfaces, enums are counted directly

Fields, enum members and typedefs are indexed but not part of the §5.2 count
set.
"""

from collections import Counter
from collections.abc import Iterable

from cii.core.enums import SymbolType
from cii.core.models import SymbolCounts

_CLASS_LIKE = {SymbolType.CLASS, SymbolType.RECORD}
_STRUCTURE_LIKE = {SymbolType.STRUCT, SymbolType.UNION}
_METHOD_LIKE = {SymbolType.METHOD, SymbolType.CONSTRUCTOR, SymbolType.DESTRUCTOR}


def compute_counts(
    symbol_types: Iterable[SymbolType | str], namespace_count: int = 0
) -> SymbolCounts:
    """Compute per-file symbol counts from symbol types (parse output or rows)."""
    counter: Counter[SymbolType] = Counter(
        symbol_type if isinstance(symbol_type, SymbolType) else SymbolType(symbol_type)
        for symbol_type in symbol_types
    )
    return SymbolCounts(
        namespaces=namespace_count,
        classes=sum(counter[kind] for kind in _CLASS_LIKE),
        structures=sum(counter[kind] for kind in _STRUCTURE_LIKE),
        interfaces=counter[SymbolType.INTERFACE],
        enums=counter[SymbolType.ENUM],
        functions=counter[SymbolType.FUNCTION],
        methods=sum(counter[kind] for kind in _METHOD_LIKE),
        properties=counter[SymbolType.PROPERTY],
    )
