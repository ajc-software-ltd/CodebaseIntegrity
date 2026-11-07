"""Filesystem ↔ database reconciliation (PLAN.md §10.3).

Deterministic comparison of what is on disk against what is indexed. The
comparison re-uses the scanner's change detection (content hashes are
authoritative, renames pair by hash) but never writes anything — validation
is read-only.
"""

from pathlib import Path

from cii.core.configuration import CiiConfig
from cii.core.models import FileRecord
from cii.database.database import Database
from cii.database.repositories import FileRepository, ProjectRepository
from cii.scanner.change_detector import ChangeSet, detect_changes
from cii.scanner.discovery import discover
from cii.scanner.file_filter import FileFilter
from cii.scanner.file_hash import hash_file


def reconcile(project_root: Path, config: CiiConfig, database: Database) -> ChangeSet:
    """Compare filesystem state with database records.

    Every eligible file is re-hashed (validation never trusts timestamps).
    """
    project = ProjectRepository(database.connection).get_by_root(str(project_root))
    if project is None:
        from cii.core.exceptions import ProjectRootError

        raise ProjectRootError(f"project not registered in CII: {project_root}")

    file_filter = FileFilter(config.scan, config.languages)
    candidates, _stats = discover(
        project_root,
        file_filter,
        follow_symlinks=config.scan.follow_symlinks,
    )
    current: list[FileRecord] = []
    for candidate in candidates:
        candidate.content_hash = hash_file(
            project_root / candidate.relative_path, config.scan.hash_algorithm
        )
        current.append(candidate)

    rows = FileRepository(database.connection).list_all(project.project_id)
    return detect_changes(current, rows)
