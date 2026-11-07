"""Target resolution for relationship references.

A parser records relationship evidence as names (``SymbolReference.target_name``).
The resolver maps those names to indexed symbols. Resolution order:

1. exact fully qualified name match,
2. exact simple name match when unambiguous,
3. trailing-component match when unambiguous.

Template arguments and reference/pointer decorations are stripped before
matching (``Base<T>`` → ``Base``). Unresolvable names are reported — a
relationship is stored only when the target exists in the index (the schema
requires a target symbol id).
"""

import re

from cii.database.models import SymbolRow

_TEMPLATE_RE = re.compile(r"<.*>", re.DOTALL)


def normalise_target_name(name: str) -> str:
    """Strip template arguments and pointer/reference decorations."""
    cleaned = _TEMPLATE_RE.sub("", name).strip()
    return cleaned.rstrip("*& ").strip()


def resolve_target(target_name: str, candidates: list[SymbolRow]) -> SymbolRow | None:
    """Resolve a reference name against indexed symbols, or None."""
    wanted = normalise_target_name(target_name)
    if not wanted:
        return None

    exact = [row for row in candidates if row.fully_qualified_name == wanted]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return exact[0]

    simple_matches = [row for row in candidates if row.symbol_name == wanted]
    if len(simple_matches) == 1:
        return simple_matches[0]

    trailing = [
        row for row in candidates
        if row.fully_qualified_name.endswith(f"::{wanted}")
        or row.fully_qualified_name.endswith(f".{wanted}")
    ]
    if len(trailing) == 1:
        return trailing[0]
    return None
