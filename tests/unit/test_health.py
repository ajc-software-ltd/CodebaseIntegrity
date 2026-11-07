"""Tests for integrity status determination (PLAN.md §10.2)."""

from cii.core.enums import FindingSeverity, IntegrityStatus
from cii.core.models import IntegrityFinding
from cii.integrity.health import determine_status, summarise


def _finding(code: str, severity: FindingSeverity = FindingSeverity.WARNING,
             message: str = "x") -> IntegrityFinding:
    return IntegrityFinding(code=code, severity=severity, message=message)


class TestDetermineStatus:
    def test_empty_is_healthy(self) -> None:
        assert determine_status([]) is IntegrityStatus.HEALTHY

    def test_database_error(self) -> None:
        findings = [_finding("database_inconsistency", FindingSeverity.ERROR)]
        assert determine_status(findings) is IntegrityStatus.ERROR

    def test_duplicates_are_error(self) -> None:
        findings = [_finding("duplicate_declaration", FindingSeverity.ERROR)]
        assert determine_status(findings) is IntegrityStatus.ERROR

    def test_parser_failure_is_incomplete(self) -> None:
        findings = [_finding("parser_failure")]
        assert determine_status(findings) is IntegrityStatus.INCOMPLETE

    def test_pending_is_incomplete(self) -> None:
        findings = [_finding("pending_index")]
        assert determine_status(findings) is IntegrityStatus.INCOMPLETE

    def test_changed_hash_is_stale(self) -> None:
        findings = [_finding("changed_hash")]
        assert determine_status(findings) is IntegrityStatus.STALE

    def test_incomplete_wins_over_stale(self) -> None:
        findings = [_finding("changed_hash"), _finding("pending_index")]
        assert determine_status(findings) is IntegrityStatus.INCOMPLETE

    def test_error_wins_over_everything(self) -> None:
        findings = [
            _finding("changed_hash"),
            _finding("pending_index"),
            _finding("duplicate_declaration", FindingSeverity.ERROR),
        ]
        assert determine_status(findings) is IntegrityStatus.ERROR

    def test_warning_only(self) -> None:
        findings = [_finding("stale_markdown")]
        assert determine_status(findings) is IntegrityStatus.WARNING


class TestSummarise:
    def test_counts(self) -> None:
        summary = summarise(
            [
                _finding("a", FindingSeverity.ERROR),
                _finding("b", FindingSeverity.WARNING),
                _finding("c", FindingSeverity.WARNING),
            ],
            files_checked=4,
            validation_time=1.5,
            full_scan=True,
        )
        assert summary.errors == 1
        assert summary.warnings == 2
        assert summary.files_checked == 4
        assert summary.full_scan is True

    def test_failed_validation(self) -> None:
        summary = summarise(
            [], files_checked=0, validation_time=0.1, full_scan=False, failed=True
        )
        assert summary.status is IntegrityStatus.FAILED
