"""Integrity status determination (PLAN.md §10.2).

Status precedence (worst wins):

- FAILED     — the validation operation itself could not complete;
- ERROR      — structural inconsistencies (duplicates, DB problems);
- INCOMPLETE — some eligible files are not successfully indexed
               (failed, pending, or unsupported records);
- STALE      — files changed on disk since indexing (missing/unindexed/
               changed-hash/renamed evidence);
- WARNING    — non-critical inconsistencies only;
- HEALTHY    — index matches the latest successful scan.

HEALTHY is never reported when files failed parsing or validation was
incomplete (PLAN.md §10.2).
"""

from pydantic import BaseModel, Field

from cii.core.enums import FindingSeverity, IntegrityStatus
from cii.core.models import IntegrityFinding

_STALE_CODES = {"missing_file", "unindexed_file", "changed_hash", "renamed_file"}
_INCOMPLETE_CODES = {"parser_failure", "pending_index", "unsupported_file"}


class HealthSummary(BaseModel):
    """Assembled validation result."""

    status: IntegrityStatus
    findings: list[IntegrityFinding] = Field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    files_checked: int = 0
    validation_time: float = 0.0
    full_scan: bool = False


def determine_status(findings: list[IntegrityFinding]) -> IntegrityStatus:
    """Derive the overall integrity status from findings."""
    codes = {finding.code for finding in findings}
    has_errors = any(f.severity is FindingSeverity.ERROR for f in findings)
    has_warnings = any(f.severity is FindingSeverity.WARNING for f in findings)

    if codes & {"database_inconsistency", "duplicate_declaration", "conflicting_declaration"}:
        return IntegrityStatus.ERROR
    if codes & _INCOMPLETE_CODES:
        return IntegrityStatus.INCOMPLETE
    if codes & _STALE_CODES:
        return IntegrityStatus.STALE
    if has_errors:
        return IntegrityStatus.ERROR
    if has_warnings:
        return IntegrityStatus.WARNING
    return IntegrityStatus.HEALTHY


def summarise(
    findings: list[IntegrityFinding],
    *,
    files_checked: int,
    validation_time: float,
    full_scan: bool,
    failed: bool = False,
) -> HealthSummary:
    """Build a :class:`HealthSummary` from findings."""
    if failed:
        status = IntegrityStatus.FAILED
    else:
        status = determine_status(findings)
    return HealthSummary(
        status=status,
        findings=findings,
        errors=sum(1 for f in findings if f.severity is FindingSeverity.ERROR),
        warnings=sum(1 for f in findings if f.severity is FindingSeverity.WARNING),
        files_checked=files_checked,
        validation_time=validation_time,
        full_scan=full_scan,
    )
