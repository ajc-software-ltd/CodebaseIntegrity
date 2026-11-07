"""Relationship construction from parser evidence.

Relationships are recorded only when supported by parser or semantic-analysis
evidence (PLAN.md §6.2). v0.1 builds:

- ``contains``   — structural nesting (parent symbol → child symbol),
- ``inherits``   — base-class evidence from the parser,
- ``implements`` — interface-list evidence from the parser.

``calls`` and ``references`` require call-graph analysis and belong to future
development (PLAN.md §22.1) — they are never fabricated here.
"""

from cii.database.models import SymbolRow
from cii.database.repositories import RelationshipRepository
from cii.indexer.symbol_resolver import resolve_target
from cii.parsers.base import SymbolReference

CONTAINS = "contains"


def build_contains_edges(relationship_repo: RelationshipRepository,
                         rows: list[SymbolRow]) -> int:
    """Record contains edges for symbols with a parent in the same file."""
    ids = {int(row.symbol_id) for row in rows if row.symbol_id is not None}
    created = 0
    for row in rows:
        if row.parent_symbol_id is not None and row.symbol_id is not None:
            if int(row.symbol_id) in ids:
                relationship_repo.add(
                    int(row.parent_symbol_id),
                    int(row.symbol_id),
                    CONTAINS,
                    confidence=1.0,
                )
                created += 1
    return created


def build_reference_edges(
    relationship_repo: RelationshipRepository,
    references: list[SymbolReference],
    source_rows: list[SymbolRow],
    project_candidates: list[SymbolRow],
) -> tuple[int, int]:
    """Resolve and record inherit/implement edges.

    Returns ``(recorded, unresolved)`` counts. Unresolved names are not stored
    (the schema requires a target symbol id) but are surfaced for reporting.
    """
    source_by_fqn = {row.fully_qualified_name: int(row.symbol_id) for row in source_rows
                     if row.symbol_id is not None}
    recorded = 0
    unresolved = 0
    for reference in references:
        source_id = source_by_fqn.get(reference.source_fqn)
        target = resolve_target(reference.target_name, project_candidates)
        if source_id is None or target is None or target.symbol_id is None:
            unresolved += 1
            continue
        relationship_repo.add(
            source_id,
            int(target.symbol_id),
            reference.relationship_type.value,
            confidence=reference.confidence,
        )
        recorded += 1
    return recorded, unresolved
