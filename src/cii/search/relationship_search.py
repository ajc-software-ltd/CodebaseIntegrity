"""Relationship queries (PLAN.md §11.1, §12.1 tool `index_dependencies`).

Returns only relationships backed by stored evidence — anything the parser
could not prove is not in the database, so nothing is invented here. Both
directions are included (the symbol may be source or target).
"""

from pydantic import BaseModel

from cii.database.database import Database
from cii.database.models import SymbolRow


class RelatedSymbol(BaseModel):
    name: str
    fully_qualified_name: str
    symbol_type: str
    file_path: str


class RelationshipHit(BaseModel):
    relationship_type: str
    confidence: float
    direction: str  # "outgoing" | "incoming"
    source: RelatedSymbol
    target: RelatedSymbol


class RelationshipPage(BaseModel):
    total: int
    offset: int
    limit: int
    results: list[RelationshipHit]


def search_relationships(
    database: Database,
    project_id: str,
    symbol_name: str,
    *,
    relationship_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> RelationshipPage:
    """Known relationships for a symbol, matched by name or fully qualified name."""
    matches = database.connection.execute(
        "SELECT s.*, f.relative_path AS file_path FROM symbols s "
        "JOIN files f ON f.file_id = s.file_id "
        "WHERE f.project_id = ? AND (s.symbol_name = ? OR s.fully_qualified_name = ?) "
        "ORDER BY s.fully_qualified_name, s.symbol_id",
        (project_id, symbol_name, symbol_name),
    ).fetchall()
    symbol_ids = [int(row["symbol_id"]) for row in matches]
    if not symbol_ids:
        return RelationshipPage(total=0, offset=offset, limit=limit, results=[])

    hits: list[RelationshipHit] = []
    id_placeholders = ", ".join("?" for _ in symbol_ids)
    types_clause = ""
    type_params: list[object] = []
    if relationship_types:
        type_placeholders = ", ".join("?" for _ in relationship_types)
        types_clause = f" AND relationship_type IN ({type_placeholders})"
        type_params = list(relationship_types)
    rows = database.connection.execute(
        "SELECT * FROM relationships "
        f"WHERE (source_symbol_id IN ({id_placeholders}) "
        f"OR target_symbol_id IN ({id_placeholders})){types_clause} "
        "ORDER BY relationship_id",
        [*symbol_ids, *symbol_ids, *type_params],
    ).fetchall()
    for row in rows:
        source = _symbol_with_file(database, int(row["source_symbol_id"]))
        target = _symbol_with_file(database, int(row["target_symbol_id"]))
        if source is None or target is None:
            continue
        outgoing = int(row["source_symbol_id"]) in set(symbol_ids)
        hits.append(RelationshipHit(
            relationship_type=row["relationship_type"],
            confidence=row["confidence"],
            direction="outgoing" if outgoing else "incoming",
            source=_related(source[0], source[1]),
            target=_related(target[0], target[1]),
        ))

    seen: set[tuple[str, str, str]] = set()
    unique: list[RelationshipHit] = []
    for hit in hits:
        key = (hit.source.fully_qualified_name, hit.target.fully_qualified_name,
               hit.relationship_type)
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    page = unique[offset: offset + limit]
    return RelationshipPage(
        total=len(unique), offset=offset, limit=limit, results=page
    )


def _symbol_with_file(database: Database, symbol_id: int) -> tuple[SymbolRow, str] | None:
    row = database.connection.execute(
        "SELECT s.*, f.relative_path AS file_path FROM symbols s "
        "JOIN files f ON f.file_id = s.file_id WHERE s.symbol_id = ?",
        (symbol_id,),
    ).fetchone()
    if row is None:
        return None
    return SymbolRow(
        symbol_id=row["symbol_id"],
        file_id=row["file_id"],
        parent_symbol_id=row["parent_symbol_id"],
        symbol_name=row["symbol_name"],
        fully_qualified_name=row["fully_qualified_name"],
        symbol_type=row["symbol_type"],
        visibility=row["visibility"],
        signature=row["signature"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        fingerprint=row["fingerprint"],
    ), row["file_path"]


def _related(symbol: SymbolRow, file_path: str) -> RelatedSymbol:
    return RelatedSymbol(
        name=symbol.symbol_name,
        fully_qualified_name=symbol.fully_qualified_name,
        symbol_type=symbol.symbol_type,
        file_path=file_path,
    )
