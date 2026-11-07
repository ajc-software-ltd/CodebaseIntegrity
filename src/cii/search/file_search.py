"""File search (PLAN.md §11.1).

Locates indexed files by filename, path fragment or language, paginated like
symbol search so responses stay concise.
"""

from pydantic import BaseModel

from cii.database.database import Database


class FileSearchHit(BaseModel):
    """One file located by search."""

    relative_path: str
    filename: str
    language: str
    file_status: str
    content_hash: str | None = None
    file_size: int | None = None
    last_scanned: float | None = None


class FileSearchPage(BaseModel):
    total: int
    offset: int
    limit: int
    results: list[FileSearchHit]


def search_files(
    database: Database,
    project_id: str,
    query: str,
    *,
    language: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> FileSearchPage:
    """Search indexed files by name or path fragment (case-insensitive)."""
    like = f"%{query.lower()}%"
    where = ["project_id = ?", "(LOWER(filename) LIKE ? OR LOWER(relative_path) LIKE ?)"]
    params: list[object] = [project_id, like, like]
    if language is not None:
        where.append("language = ?")
        params.append(language)
    where_sql = " AND ".join(where)

    total = int(database.connection.execute(
        f"SELECT COUNT(*) FROM files WHERE {where_sql}", params
    ).fetchone()[0])
    rows = database.connection.execute(
        "SELECT relative_path, filename, language, scan_status, content_hash, "
        "file_size, last_scanned FROM files "
        f"WHERE {where_sql} ORDER BY relative_path LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return FileSearchPage(
        total=total,
        offset=offset,
        limit=limit,
        results=[
            FileSearchHit(
                relative_path=row["relative_path"],
                filename=row["filename"],
                language=row["language"],
                file_status=row["scan_status"],
                content_hash=row["content_hash"],
                file_size=row["file_size"],
                last_scanned=row["last_scanned"],
            )
            for row in rows
        ],
    )
