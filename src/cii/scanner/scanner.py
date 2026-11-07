"""Scan orchestration.

Brings the persisted file index in line with the filesystem: discovery →
hashing (with an unchanged-file fast path) → change detection → transactional
database update → scan-history record (PLAN.md §7, §9.1).

Symbol parsing and indexing are layered on top in later milestones; this
module owns the file-level state (paths, hashes, scan status).
"""

import time
from pathlib import Path

from pydantic import BaseModel

from cii.core.configuration import CiiConfig
from cii.core.models import FileRecord
from cii.database.database import Database
from cii.database.models import FileRow
from cii.database.repositories import (
    FileRepository,
    ProjectRepository,
    ScanHistoryRepository,
)
from cii.database.transactions import transaction
from cii.scanner.change_detector import ChangeSet, detect_changes
from cii.scanner.discovery import DiscoveryStats, discover
from cii.scanner.file_filter import FileFilter
from cii.scanner.file_hash import hash_file

#: Scan status of a file whose content is current but whose symbols have not
#: been (re)indexed yet.
PENDING_STATUS = "pending"


class ScanResult(BaseModel):
    """Outcome of one scan cycle."""

    scan_id: int
    full: bool
    changes: ChangeSet
    discovery: DiscoveryStats
    hashed_files: int = 0
    hash_skips: int = 0


class Scanner:
    """File-level scanner for one project."""

    def __init__(self, project_root: Path, config: CiiConfig, database: Database) -> None:
        self._project_root = project_root
        self._config = config
        self._database = database

    def scan(self, full: bool = False) -> ScanResult:
        """Run one scan cycle and persist the resulting file state.

        With ``full=False`` a file whose size and modification time match the
        indexed record is treated as unchanged without re-hashing (content
        hashes stay authoritative whenever anything differs). With
        ``full=True`` every eligible file is re-hashed.

        Raises:
            ProjectRootError: the project is not registered (run ``cii init``).
        """
        project_repo = ProjectRepository(self._database.connection)
        project = project_repo.get_by_root(str(self._project_root))
        if project is None:
            from cii.core.exceptions import ProjectRootError

            raise ProjectRootError(
                f"project not registered in CII: {self._project_root} (run 'cii init')"
            )

        file_filter = FileFilter(self._config.scan, self._config.languages)
        candidates, stats = discover(
            self._project_root,
            file_filter,
            follow_symlinks=self._config.scan.follow_symlinks,
        )

        file_repo = FileRepository(self._database.connection)
        rows = file_repo.list_all(project.project_id)
        rows_by_path = {row.relative_path: row for row in rows}

        current, hashed, hash_skips = self._resolve_hashes(candidates, rows_by_path, full)
        changes = detect_changes(current, rows_by_path.values())

        scan_type = "full" if full else "incremental"
        history_repo = ScanHistoryRepository(self._database.connection)
        with transaction(self._database.connection):
            scan = history_repo.start(project.project_id, scan_type)
            self._apply_changes(project.project_id, current, rows_by_path, changes)
            history_repo.finish(
                int(scan.scan_id),  # type: ignore[arg-type]
                files_processed=len(current),
                files_failed=0,
                status="completed",
            )
            project_repo.set_last_scan(project.project_id)

        return ScanResult(
            scan_id=int(scan.scan_id),  # type: ignore[arg-type]
            full=full,
            changes=changes,
            discovery=stats,
            hashed_files=hashed,
            hash_skips=hash_skips,
        )

    def _resolve_hashes(
        self,
        candidates: list[FileRecord],
        rows_by_path: dict[str, FileRow],
        full: bool,
    ) -> tuple[list[FileRecord], int, int]:
        """Fill in content hashes, skipping unchanged files on incremental scans."""
        hashed = 0
        hash_skips = 0
        current: list[FileRecord] = []
        for candidate in candidates:
            row = rows_by_path.get(candidate.relative_path)
            fast_path = (
                not full
                and row is not None
                and row.content_hash is not None
                and row.file_size == candidate.file_size
                and row.modified_at == candidate.modified_at
            )
            if fast_path:
                candidate.content_hash = row.content_hash
                hash_skips += 1
            else:
                candidate.content_hash = hash_file(
                    self._project_root / candidate.relative_path,
                    self._config.scan.hash_algorithm,
                )
                hashed += 1
            current.append(candidate)
        return current, hashed, hash_skips

    def _apply_changes(
        self,
        project_id: str,
        current: list[FileRecord],
        rows_by_path: dict[str, FileRow],
        changes: ChangeSet,
    ) -> None:
        """Persist the change set. Runs inside the scan transaction."""
        file_repo = FileRepository(self._database.connection)
        now = time.time()
        current_by_path = {record.relative_path: record for record in current}

        for rename in changes.renamed:
            row = rows_by_path[rename.old_relative_path]
            record = current_by_path[rename.new_relative_path]
            # A pure rename keeps file_id (and with it any indexed symbols):
            # only the path and freshness metadata change.
            file_repo.upsert(
                FileRow(
                    file_id=row.file_id,
                    project_id=project_id,
                    relative_path=record.relative_path,
                    filename=record.filename,
                    extension=record.extension,
                    language=record.language.value,
                    content_hash=record.content_hash,
                    file_size=record.file_size,
                    modified_at=record.modified_at,
                    last_scanned=now,
                    scan_status=PENDING_STATUS,
                    parser_version=row.parser_version,
                )
            )

        for record in [*changes.added, *changes.modified]:
            file_repo.upsert(
                FileRow(
                    project_id=project_id,
                    relative_path=record.relative_path,
                    filename=record.filename,
                    extension=record.extension,
                    language=record.language.value,
                    content_hash=record.content_hash,
                    file_size=record.file_size,
                    modified_at=record.modified_at,
                    last_scanned=now,
                    scan_status=PENDING_STATUS,
                )
            )

        for relative_path in changes.deleted:
            file_repo.delete(project_id, relative_path)
