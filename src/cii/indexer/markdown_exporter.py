"""Markdown index export (PLAN.md §14).

Generates ``.cii/CODEBASE_INDEX.md`` from the database — the Markdown file is
generated output, never maintained by hand, and the database remains the
authoritative source. The export contains structural information only: no
function bodies, no source implementations.

Output is deterministic (files ordered by path, symbols by line then name) so
unchanged indexes regenerate byte-identically and are skipped when unchanged
(PLAN.md §17.2).
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from cii.core.configuration import CiiConfig
from cii.core.models import SymbolCounts
from cii.database.database import Database
from cii.database.models import FileRow
from cii.database.repositories import (
    FileRepository,
    NamespaceRepository,
    ProjectRepository,
    SymbolRepository,
)
from cii.indexer.symbol_extractor import compute_counts

INDEX_FILE_NAME = "CODEBASE_INDEX.md"
INDEXES_DIR_NAME = "indexes"

_SECTION_KEYS = (
    ("CLASSES", ("class", "record")),
    ("STRUCTURES", ("struct", "union")),
    ("INTERFACES", ("interface",)),
    ("ENUMS", ("enum",)),
    ("PROPERTIES", ("property",)),
    ("FUNCTIONS", ("function",)),
    ("TYPEDEFS", ("typedef",)),
    ("EVENTS", ("event",)),
    ("DELEGATES", ("delegate",)),
)
_METHOD_TYPES = {"method", "constructor", "destructor"}
_LANGUAGE_LABELS = {
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "python": "Python",
    "unknown": "Unknown",
}


@dataclass
class _FileRenderData:
    file_row: FileRow
    counts: SymbolCounts
    namespaces: list[str]
    categories: dict[str, list[str]] = field(default_factory=dict)
    methods_by_parent: dict[str, list[str]] = field(default_factory=dict)
    symbol_rows: int = 0


def export_index(database: Database, project_root: Path, config: CiiConfig) -> list[Path]:
    """Regenerate the Markdown index; returns the paths actually written.

    Writes nothing when the generated content is unchanged.
    """
    project = ProjectRepository(database.connection).get_by_root(str(project_root))
    if project is None:
        from cii.core.exceptions import ProjectRootError

        raise ProjectRootError(f"project not registered in CII: {project_root}")

    files = FileRepository(database.connection).list_all(project.project_id)
    written: list[Path] = []
    index_path = project_root / ".cii" / INDEX_FILE_NAME
    document = _render_document(database, project.project_name, project.index_version, files)
    if _write_if_changed(index_path, document):
        written.append(index_path)

    if config.output.split_by_language:
        by_language: dict[str, list[FileRow]] = {}
        for file_row in files:
            by_language.setdefault(file_row.language, []).append(file_row)
        for language in sorted(by_language):
            sub_document = _render_document(
                database,
                project.project_name,
                project.index_version,
                by_language[language],
                scope=language,
            )
            sub_path = project_root / ".cii" / INDEXES_DIR_NAME / f"{language}.md"
            if _write_if_changed(sub_path, sub_document):
                written.append(sub_path)
    return written


def _write_if_changed(path: Path, content: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _collect_file_data(database: Database, file_row: FileRow) -> _FileRenderData:
    symbol_repo = SymbolRepository(database.connection)
    namespace_repo = NamespaceRepository(database.connection)
    rows = symbol_repo.list_by_file(int(file_row.file_id))
    names_by_id = {
        int(row.symbol_id): row.symbol_name for row in rows if row.symbol_id is not None
    }
    namespaces = [
        entry.namespace_name
        for entry in namespace_repo.list_by_file(int(file_row.file_id))
    ]
    counts = compute_counts((row.symbol_type for row in rows), len(namespaces))

    data = _FileRenderData(
        file_row=file_row,
        counts=counts,
        namespaces=namespaces,
        symbol_rows=len(rows),
    )
    for row in sorted(rows, key=lambda r: (r.start_line or 0, r.symbol_name)):
        if row.symbol_type in _METHOD_TYPES:
            parent = names_by_id.get(
                int(row.parent_symbol_id) if row.parent_symbol_id is not None else -1,
                "<global>",
            )
            data.methods_by_parent.setdefault(parent, []).append(row.symbol_name)
        else:
            data.categories.setdefault(row.symbol_type, []).append(
                row.fully_qualified_name
            )
    return data


def _render_document(
    database: Database,
    project_name: str,
    index_version: str,
    files: list[FileRow],
    *,
    scope: str | None = None,
) -> str:
    per_file = [_collect_file_data(database, file_row) for file_row in files]

    total_counts = SymbolCounts()
    total_rows = 0
    for data in per_file:
        total_rows += data.symbol_rows
        total_counts = total_counts.model_copy(update={
            name: getattr(total_counts, name) + getattr(data.counts, name)
            for name in SymbolCounts.model_fields
        })

    lines: list[str] = []
    header_scope = f" ({scope})" if scope else ""
    lines.append(f"# CODEBASE INDEX{header_scope}")
    lines.append("")
    lines.append(f"PROJECT: {project_name}")
    lines.append(f"INDEX_VERSION: {index_version}")
    lines.append(f"LAST_UPDATED: {_format_time(time.time())}")
    lines.append(f"FILES: {len(files)}")
    lines.append(f"SYMBOLS: {total_rows}")
    lines.append("")
    lines.append("[STATISTICS]")
    lines.append(f"Namespaces: {total_counts.namespaces}")
    lines.append(f"Classes: {total_counts.classes}")
    lines.append(f"Structures: {total_counts.structures}")
    lines.append(f"Interfaces: {total_counts.interfaces}")
    lines.append(f"Enums: {total_counts.enums}")
    lines.append(f"Functions: {total_counts.functions}")
    lines.append(f"Methods: {total_counts.methods}")
    lines.append(f"Properties: {total_counts.properties}")

    for data in per_file:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"FILE: {data.file_row.relative_path}")
        lines.append("")
        lines.append(f"LANGUAGE: {_language_label(data.file_row.language)}")
        lines.append("")
        lines.append(f"LAST_SCANNED: {_format_time(data.file_row.last_scanned)}")
        lines.append("")
        lines.append("[COUNTS]")
        lines.append(f"Namespaces: {data.counts.namespaces}")
        lines.append(f"Classes: {data.counts.classes}")
        lines.append(f"Structures: {data.counts.structures}")
        lines.append(f"Interfaces: {data.counts.interfaces}")
        lines.append(f"Enums: {data.counts.enums}")
        lines.append(f"Functions: {data.counts.functions}")
        lines.append(f"Methods: {data.counts.methods}")
        lines.append(f"Properties: {data.counts.properties}")
        if data.namespaces:
            lines.append("")
            lines.append("[NAMESPACES]")
            lines.extend(data.namespaces)
        for title, keys in _SECTION_KEYS:
            values = [name for key in keys for name in data.categories.get(key, [])]
            if values:
                lines.append("")
                lines.append(f"[{title}]")
                lines.extend(values)
        if data.methods_by_parent:
            lines.append("")
            lines.append("[METHODS]")
            for parent in sorted(data.methods_by_parent):
                lines.append(f"{parent}:")
                lines.extend(f"    {method}" for method in data.methods_by_parent[parent])

    lines.append("")
    return "\n".join(lines)


def _format_time(value: float | None) -> str:
    if value is None:
        return "never"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))


def _language_label(language: str) -> str:
    return _LANGUAGE_LABELS.get(language, language)
