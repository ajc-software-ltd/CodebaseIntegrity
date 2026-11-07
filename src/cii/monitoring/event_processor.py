"""Filesystem event processing (PLAN.md §9).

Turns raw changed paths into incremental rescans, and performs periodic
reconciliation so events missed by the watcher cannot silently desynchronise
the index (PLAN.md §9.2, §18.3).
"""

import time
from pathlib import Path

from pydantic import BaseModel

from cii.application import Application, ScanOutcome
from cii.core.configuration import CiiConfig
from cii.integrity.reconciliation import reconcile

# Temporary/editor artefacts that never indicate real source changes.
_TEMP_SUFFIXES = ("~", ".swp", ".swx", ".tmp", ".part", ".swpx", ".new")
_TEMP_PREFIXES = (".#", ".goutputstream-")


def is_temporary_path(path: str | Path) -> bool:
    name = Path(path).name
    return name.endswith(_TEMP_SUFFIXES) or name.startswith(_TEMP_PREFIXES)


class ProcessResult(BaseModel):
    """Outcome of processing one event batch."""

    relevant_paths: list[str] = []
    scan_triggered: bool = False
    scan: ScanOutcome | None = None


class ReconcileResult(BaseModel):
    """Outcome of a periodic reconciliation check."""

    ran: bool = False
    discrepancies: int = 0
    scan_triggered: bool = False
    scan: ScanOutcome | None = None


class EventProcessor:
    """Filters events and triggers incremental rescans and reconciliations."""

    def __init__(self, application: Application, config: CiiConfig) -> None:
        self._application = application
        self._config = config
        self._next_reconcile = time.monotonic() + config.monitor.reconcile_interval_seconds

    def process_batch(self, paths: list[str]) -> ProcessResult:
        """Filter a batch of changed paths and rescan when anything is relevant.

        The rescan is incremental: unchanged files are skipped by content
        fingerprint (PLAN.md §9.1).
        """
        relevant = [
            path for path in paths
            if not is_temporary_path(path) and self._within_project(path)
        ]
        if not relevant:
            return ProcessResult(relevant_paths=[])
        outcome = self._application.scan()
        return ProcessResult(relevant_paths=relevant, scan_triggered=True, scan=outcome)

    def maybe_reconcile(self, now: float | None = None) -> ReconcileResult:
        """Run periodic reconciliation when due (recovery from missed events)."""
        current = time.monotonic() if now is None else now
        if current < self._next_reconcile:
            return ReconcileResult()
        self._next_reconcile = current + self._config.monitor.reconcile_interval_seconds
        changes = reconcile(
            self._application.project_root, self._config, self._application.database
        )
        discrepancies = (
            len(changes.added) + len(changes.modified) + len(changes.deleted)
            + len(changes.renamed)
        )
        if discrepancies == 0:
            return ReconcileResult(ran=True, discrepancies=0)
        outcome = self._application.scan()
        return ReconcileResult(
            ran=True, discrepancies=discrepancies, scan_triggered=True, scan=outcome
        )

    def _within_project(self, path: str) -> bool:
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                candidate.relative_to(self._application.project_root)
            except ValueError:
                return False
        return True
