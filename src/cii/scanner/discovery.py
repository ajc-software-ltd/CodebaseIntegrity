"""Project file discovery.

Walks the project tree applying the configured exclusion rules, symlink
policy, size limits and file classification, and produces candidate file
records for change detection (PLAN.md §7.1–§7.3).

Symlink policy: symbolic links are skipped unless ``follow_symlinks`` is
enabled; even then, only links that resolve inside the project root are
followed (PLAN.md §19.6). Directory cycles are detected and skipped.
"""

import os
from pathlib import Path

from pydantic import BaseModel

from cii.core.models import FileRecord
from cii.scanner.file_filter import FileFilter
from cii.utilities.paths import is_within_root


class DiscoveryStats(BaseModel):
    """Counters describing what discovery skipped and why."""

    discovered: int = 0
    unsupported_extension: int = 0
    too_large: int = 0
    binary: int = 0
    generated: int = 0
    symlink_skipped: int = 0
    excluded_directories: int = 0


def discover(
    project_root: Path,
    file_filter: FileFilter,
    *,
    follow_symlinks: bool = False,
) -> tuple[list[FileRecord], DiscoveryStats]:
    """Enumerate eligible source files under ``project_root``.

    Returned records carry size and modification time but no content hash;
    hashing is the scanner's decision (incremental scans can skip unchanged
    files).
    """
    stats = DiscoveryStats()
    records: list[FileRecord] = []
    # (directory, real paths of its ancestors) — cycle detection follows the
    # walk chain only, so two distinct paths to the same directory are both
    # indexed deterministically (the index is path-based).
    stack: list[tuple[Path, tuple[str, ...]]] = [(project_root, ())]

    while stack:
        directory, ancestors = stack.pop()
        real = os.path.realpath(directory)
        if real in ancestors:
            continue
        next_ancestors = (*ancestors, real)

        with os.scandir(directory) as entries:
            for entry in entries:
                is_link = entry.is_symlink()
                if is_link:
                    if not follow_symlinks or not is_within_root(entry.path, project_root):
                        stats.symlink_skipped += 1
                        continue

                if entry.is_dir(follow_symlinks=True):
                    relative_dir = os.path.relpath(entry.path, project_root)
                    if file_filter.is_excluded_directory(relative_dir):
                        stats.excluded_directories += 1
                        continue
                    stack.append((Path(entry.path), next_ancestors))
                    continue

                if not entry.is_file(follow_symlinks=True):
                    continue

                relative_path = os.path.relpath(entry.path, project_root).replace(os.sep, "/")
                language = file_filter.classify(Path(entry.path))
                if language is None:
                    stats.unsupported_extension += 1
                    continue

                file_stat = entry.stat(follow_symlinks=True)
                if file_filter.is_too_large(file_stat.st_size):
                    stats.too_large += 1
                    continue
                if file_filter.is_binary(Path(entry.path)):
                    stats.binary += 1
                    continue
                if file_filter.is_generated(Path(entry.path)):
                    stats.generated += 1
                    continue

                records.append(
                    FileRecord(
                        relative_path=relative_path,
                        filename=entry.name,
                        extension=Path(entry.name).suffix.lower(),
                        language=language,
                        file_size=file_stat.st_size,
                        modified_at=file_stat.st_mtime,
                    )
                )
                stats.discovered += 1

    records.sort(key=lambda record: record.relative_path)
    return records, stats
