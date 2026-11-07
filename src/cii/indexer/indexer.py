"""Index pipeline: parse → register symbols → build relationships (PLAN.md §9.1).

One file is processed atomically: either the fresh parse replaces that file's
index state (symbols, namespaces, relationships) in a single transaction, or
— when parsing fails — the previous valid index is retained and the file is
marked failed (PLAN.md §8.4). Symbol identity is preserved across reindexes
(see :meth:`SymbolRepository.sync_for_file`), so relationships from other
files survive.
"""

import time
from pathlib import Path

from pydantic import BaseModel

from cii.core.configuration import CiiConfig
from cii.core.enums import Language, ScanStatus
from cii.core.models import SymbolCounts
from cii.database.database import Database
from cii.database.models import FileRow
from cii.database.repositories import (
    FileRepository,
    NamespaceRepository,
    ProjectRepository,
    RelationshipRepository,
    SymbolRepository,
)
from cii.database.transactions import transaction
from cii.indexer.relationship_builder import build_contains_edges, build_reference_edges
from cii.indexer.symbol_extractor import compute_counts
from cii.parsers.base import ParseIssue
from cii.parsers.registry import ParserRegistry, default_registry
from cii.utilities.paths import require_within_root


class FileIndexOutcome(BaseModel):
    """What happened to one file during indexing."""

    relative_path: str
    status: str  # "indexed" | "failed" | "unsupported"
    symbols_indexed: int = 0
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_removed: int = 0
    relationships_recorded: int = 0
    relationships_unresolved: int = 0
    retained_previous_index: bool = False
    issues: list[ParseIssue] = []


class IndexResult(BaseModel):
    """Aggregate outcome of an indexing pass."""

    files_indexed: int = 0
    files_failed: int = 0
    files_unsupported: int = 0
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_removed: int = 0
    relationships_recorded: int = 0
    relationships_unresolved: int = 0
    outcomes: list[FileIndexOutcome] = []


class Indexer:
    """Turns parsed files into persistent structural index state."""

    def __init__(
        self,
        project_root: Path,
        config: CiiConfig,
        database: Database,
        registry: ParserRegistry | None = None,
    ) -> None:
        self._project_root = project_root
        self._config = config
        self._database = database
        self._registry = registry or default_registry()

    def index_pending(self, *, force_all: bool = False) -> IndexResult:
        """Index every file that needs it (pending/failed, or all when forced)."""
        project = ProjectRepository(self._database.connection).get_by_root(
            str(self._project_root)
        )
        if project is None:
            from cii.core.exceptions import ProjectRootError

            raise ProjectRootError(
                f"project not registered in CII: {self._project_root} (run 'cii init')"
            )
        files = FileRepository(self._database.connection).list_all(project.project_id)
        result = IndexResult()
        for file_row in files:
            if not force_all and file_row.scan_status not in (
                ScanStatus.PENDING.value,
                ScanStatus.FAILED.value,
            ):
                continue
            outcome = self.index_file(project.project_id, file_row)
            result.outcomes.append(outcome)
            if outcome.status == "indexed":
                result.files_indexed += 1
                result.symbols_added += outcome.symbols_added
                result.symbols_updated += outcome.symbols_updated
                result.symbols_removed += outcome.symbols_removed
                result.relationships_recorded += outcome.relationships_recorded
                result.relationships_unresolved += outcome.relationships_unresolved
            elif outcome.status == "failed":
                result.files_failed += 1
            else:
                result.files_unsupported += 1
        return result

    def index_file(self, project_id: str, file_row: FileRow) -> FileIndexOutcome:
        """Parse and index one file atomically."""
        assert file_row.file_id is not None
        parser = self._registry.get(Language(file_row.language))
        if parser is None:
            self._update_file_status(file_row, ScanStatus.UNSUPPORTED, parser_version=None)
            return FileIndexOutcome(relative_path=file_row.relative_path, status="unsupported")

        absolute = require_within_root(self._project_root / file_row.relative_path,
                                       self._project_root)
        result = parser.parse(absolute, file_row.relative_path)
        if not result.ok:
            # Parser failure: retain the previous valid index (PLAN.md §8.4).
            self._update_file_status(
                file_row, ScanStatus.FAILED, parser_version=result.parser_version
            )
            return FileIndexOutcome(
                relative_path=file_row.relative_path,
                status="failed",
                retained_previous_index=True,
                issues=result.issues,
            )

        symbol_repo = SymbolRepository(self._database.connection)
        namespace_repo = NamespaceRepository(self._database.connection)
        relationship_repo = RelationshipRepository(self._database.connection)

        before_ids = {
            int(row.symbol_id) for row in symbol_repo.list_by_file(file_row.file_id)
        }
        with transaction(self._database.connection):
            ids_by_fqn = symbol_repo.sync_for_file(file_row.file_id, result.symbols)
            namespace_repo.replace_for_file(file_row.file_id, result.namespaces)
            relationship_repo.delete_sourced_in_file(file_row.file_id)
            rows = symbol_repo.list_by_file(file_row.file_id)
            build_contains_edges(relationship_repo, rows)
            recorded, unresolved = build_reference_edges(
                relationship_repo,
                result.references,
                source_rows=rows,
                project_candidates=symbol_repo.list_for_project(project_id),
            )
            self._update_file_status(
                file_row, ScanStatus.INDEXED, parser_version=result.parser_version
            )

        after_ids = set(ids_by_fqn.values())
        return FileIndexOutcome(
            relative_path=file_row.relative_path,
            status="indexed",
            symbols_indexed=len(after_ids),
            symbols_added=len(after_ids - before_ids),
            symbols_updated=len(after_ids & before_ids),
            symbols_removed=len(before_ids - after_ids),
            relationships_recorded=recorded,
            relationships_unresolved=unresolved,
            issues=result.issues,
        )

    def _update_file_status(
        self,
        file_row: FileRow,
        status: ScanStatus,
        *,
        parser_version: str | None,
    ) -> None:
        FileRepository(self._database.connection).upsert(
            FileRow(
                file_id=file_row.file_id,
                project_id=file_row.project_id,
                relative_path=file_row.relative_path,
                filename=file_row.filename,
                extension=file_row.extension,
                language=file_row.language,
                content_hash=file_row.content_hash,
                file_size=file_row.file_size,
                modified_at=file_row.modified_at,
                last_scanned=time.time(),
                scan_status=status.value,
                parser_version=parser_version,
            )
        )


def counts_for_file(database: Database, file_id: int) -> SymbolCounts:
    """Compute a file's symbol counts straight from its indexed rows."""
    symbol_repo = SymbolRepository(database.connection)
    namespace_repo = NamespaceRepository(database.connection)
    rows = symbol_repo.list_by_file(file_id)
    namespaces = namespace_repo.list_by_file(file_id)
    return compute_counts((row.symbol_type for row in rows), len(namespaces))
