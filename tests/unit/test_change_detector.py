"""Tests for change detection."""

from cii.core.enums import Language
from cii.core.models import FileRecord
from cii.database.models import FileRow
from cii.scanner.change_detector import detect_changes


def _record(path: str, content_hash: str) -> FileRecord:
    return FileRecord(
        relative_path=path,
        filename=path.rsplit("/", 1)[-1],
        extension=".py",
        language=Language.PYTHON,
        content_hash=content_hash,
    )


def _row(path: str, content_hash: str, file_id: int = 1) -> FileRow:
    return FileRow(
        file_id=file_id,
        project_id="p",
        relative_path=path,
        filename=path.rsplit("/", 1)[-1],
        extension=".py",
        language="python",
        content_hash=content_hash,
    )


class TestDetectChanges:
    def test_added(self) -> None:
        changes = detect_changes([_record("a.py", "h1")], [])
        assert [record.relative_path for record in changes.added] == ["a.py"]
        assert changes.unchanged_count == 0

    def test_modified_and_unchanged(self) -> None:
        current = [_record("a.py", "new"), _record("b.py", "same")]
        existing = [_row("a.py", "old"), _row("b.py", "same")]
        changes = detect_changes(current, existing)
        assert [record.relative_path for record in changes.modified] == ["a.py"]
        assert changes.unchanged_count == 1

    def test_deleted(self) -> None:
        changes = detect_changes([], [_row("a.py", "h1")])
        assert changes.deleted == ["a.py"]

    def test_renamed_matched_by_hash(self) -> None:
        current = [_record("b.py", "h1")]
        existing = [_row("a.py", "h1")]
        changes = detect_changes(current, existing)
        assert len(changes.renamed) == 1
        assert changes.renamed[0].old_relative_path == "a.py"
        assert changes.renamed[0].new_relative_path == "b.py"
        assert changes.added == []
        assert changes.deleted == []

    def test_hash_match_pairs_one_to_one(self) -> None:
        current = [_record("b.py", "h1"), _record("c.py", "h1")]
        existing = [_row("a.py", "h1")]
        changes = detect_changes(current, existing)
        assert len(changes.renamed) == 1
        assert changes.renamed[0].old_relative_path == "a.py"
        assert sorted(record.relative_path for record in changes.added) == ["c.py"]

    def test_unmatched_hash_stays_add_and_delete(self) -> None:
        current = [_record("b.py", "h2")]
        existing = [_row("a.py", "h1")]
        changes = detect_changes(current, existing)
        assert changes.renamed == []
        assert [record.relative_path for record in changes.added] == ["b.py"]
        assert changes.deleted == ["a.py"]

    def test_empty_hash_never_matches(self) -> None:
        current = [_record("b.py", "")]
        existing = [_row("a.py", "")]
        changes = detect_changes(current, existing)
        assert changes.renamed == []
