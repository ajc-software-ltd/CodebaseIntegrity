"""Change detection between discovered files and indexed records.

Content hashes are authoritative: a file is modified when its fingerprint
differs from the indexed fingerprint (PLAN.md §7.4). Renames are detected by
matching content hashes between disappeared and appeared paths.
"""

from pydantic import BaseModel

from cii.core.models import FileRecord
from cii.database.models import FileRow


class RenamedFile(BaseModel):
    old_relative_path: str
    new_relative_path: str


class ChangeSet(BaseModel):
    """Differences between the filesystem and the index."""

    added: list[FileRecord] = []
    modified: list[FileRecord] = []
    deleted: list[str] = []
    renamed: list[RenamedFile] = []
    unchanged_count: int = 0


def detect_changes(current: list[FileRecord], existing: list[FileRow]) -> ChangeSet:
    """Compare discovered records (with hashes) against indexed file rows.

    Rename detection pairs deleted and added paths with identical content
    hashes, one-to-one per hash; unmatched leftovers stay deleted/added.
    """
    current_by_path = {record.relative_path: record for record in current}
    existing_by_path = {row.relative_path: row for row in existing}

    added_paths = sorted(set(current_by_path) - set(existing_by_path))
    deleted_paths = sorted(set(existing_by_path) - set(current_by_path))
    shared_paths = set(current_by_path) & set(existing_by_path)

    modified: list[FileRecord] = []
    unchanged_count = 0
    for path in sorted(shared_paths):
        if current_by_path[path].content_hash != existing_by_path[path].content_hash:
            modified.append(current_by_path[path])
        else:
            unchanged_count += 1

    added_by_hash: dict[str, list[str]] = {}
    for path in added_paths:
        added_by_hash.setdefault(current_by_path[path].content_hash or "", []).append(path)
    deleted_by_hash: dict[str, list[str]] = {}
    for path in deleted_paths:
        deleted_by_hash.setdefault(existing_by_path[path].content_hash or "", []).append(path)

    renamed: list[RenamedFile] = []
    still_added: list[str] = []
    still_deleted: list[str] = []
    matched_new: set[str] = set()
    matched_old: set[str] = set()
    for content_hash in sorted(set(added_by_hash) & set(deleted_by_hash)):
        if not content_hash:
            continue  # unknown hashes must never pair as renames
        news = added_by_hash[content_hash]
        olds = deleted_by_hash[content_hash]
        for old_path, new_path in zip(olds, news, strict=False):
            renamed.append(RenamedFile(old_relative_path=old_path, new_relative_path=new_path))
            matched_new.add(new_path)
            matched_old.add(old_path)
    for path in added_paths:
        if path not in matched_new:
            still_added.append(path)
    for path in deleted_paths:
        if path not in matched_old:
            still_deleted.append(path)

    return ChangeSet(
        added=[current_by_path[path] for path in sorted(still_added)],
        modified=modified,
        deleted=sorted(still_deleted),
        renamed=renamed,
        unchanged_count=unchanged_count,
    )
