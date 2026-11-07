"""Application orchestration.

Composes the subsystems into complete operations: a scan is discovery →
change detection → transactional file update → symbol indexing → index
export (PLAN.md §9.1). Later milestones add monitoring and validation here.
"""

from pathlib import Path

from pydantic import BaseModel

from cii.core.configuration import CiiConfig, load_config
from cii.database.database import Database
from cii.database.repositories import ScanHistoryRepository
from cii.indexer.indexer import Indexer, IndexResult
from cii.indexer.markdown_exporter import export_index
from cii.scanner.scanner import Scanner, ScanResult
from cii.utilities.logging import setup_logging
from cii.utilities.paths import cii_data_dir, resolve_project_root


class ScanOutcome(BaseModel):
    """Complete result of one scan-and-index cycle."""

    scan: ScanResult
    index: IndexResult
    exported: list[str]


class Application:
    """Entry point for CII operations on one project."""

    def __init__(self, project_root: Path, config: CiiConfig, database: Database) -> None:
        self._project_root = project_root
        self._config = config
        self._database = database

    @classmethod
    def open(cls, root: Path | str, *, configure_logging: bool = False) -> "Application":
        """Open (initialise-free) the CII state of a project directory.

        Raises:
            ProjectRootError: the root is missing, or CII is not initialised
                (no database — run ``cii init``).
        """
        project_root = resolve_project_root(root)
        if configure_logging:
            config = load_config(project_root)
            setup_logging(
                level=config.logging.level,
                console=True,
                log_dir=cii_data_dir(project_root) / "logs",
            )
        return cls(project_root, load_config(project_root), Database.open(project_root))

    @property
    def database(self) -> Database:
        return self._database

    @property
    def config(self) -> CiiConfig:
        return self._config

    @property
    def project_root(self) -> Path:
        return self._project_root

    def close(self) -> None:
        self._database.close()

    def __enter__(self) -> "Application":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def scan(self, *, full: bool = False) -> ScanOutcome:
        """Run a full scan-and-index cycle and refresh the Markdown index."""
        scan_result = Scanner(self._project_root, self._config, self._database).scan(full=full)
        index_result = Indexer(self._project_root, self._config, self._database).index_pending()
        changes = scan_result.changes
        files_processed = (
            len(changes.added) + len(changes.modified) + len(changes.renamed)
            + changes.unchanged_count
        )
        ScanHistoryRepository(self._database.connection).finish(
            scan_result.scan_id,
            files_processed=files_processed,
            files_failed=index_result.files_failed,
            symbols_added=index_result.symbols_added,
            symbols_updated=index_result.symbols_updated,
            symbols_removed=index_result.symbols_removed,
            status="completed",
        )
        exported = [str(path) for path in export_index(
            self._database, self._project_root, self._config
        )]
        return ScanOutcome(scan=scan_result, index=index_result, exported=exported)

    def export(self) -> list[str]:
        """Regenerate the Markdown index from the current database state."""
        return [
            str(path)
            for path in export_index(self._database, self._project_root, self._config)
        ]
