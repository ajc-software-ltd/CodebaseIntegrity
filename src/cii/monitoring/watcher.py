"""Project filesystem watcher (PLAN.md §9.2, §9.3).

Startup behaviour: reconcile the index first (identify unindexed/changed
files and schedule their scans), then monitor. The watch loop debounces raw
filesystem events and triggers incremental rescans; periodic reconciliation
recovers from missed events. A full rebuild never happens automatically —
scans are incremental (unchanged files are skipped by content fingerprint).

The event source is injectable for testing; the default source is
``watchfiles.watch`` with the project's configured directory exclusions.
"""

import time
from collections.abc import Callable, Iterable, Iterator

from pydantic import BaseModel

from cii.application import Application, ScanOutcome
from cii.core.configuration import CiiConfig
from cii.monitoring.debounce import DebounceBuffer
from cii.monitoring.event_processor import EventProcessor, ReconcileResult
from cii.utilities.logging import get_logger

_logger = get_logger("monitoring")

# Wake the loop at least this often so debounce/reconciliation timers fire.
_WATCH_POLL_SECONDS = 0.5


class WatchSummary(BaseModel):
    """What a watch run did (returned when it stops)."""

    startup_scan: ScanOutcome | None = None
    batches_processed: int = 0
    scans_triggered: int = 0
    reconciliations: int = 0
    reconciled_discrepancies: int = 0


class ProjectWatcher:
    """Watches one project and keeps its index current."""

    def __init__(self, application: Application, config: CiiConfig) -> None:
        self._application = application
        self._config = config
        self._buffer = DebounceBuffer(
            config.monitor.debounce_seconds, config.monitor.max_debounce_seconds
        )
        self._processor = EventProcessor(application, config)

    def run(
        self,
        *,
        max_seconds: float | None = None,
        batch_source: Iterable[set[tuple[str, str]]] | None = None,
        startup_scan: bool = True,
        stop_when: Callable[[], bool] | None = None,
    ) -> WatchSummary:
        """Run the watch loop until the source is exhausted or a limit is hit.

        Args:
            max_seconds: stop after this wall-clock duration (None = forever).
            batch_source: injectable event batches (change, path) for testing;
                defaults to watchfiles on the project root.
            startup_scan: run the §9.3 startup reconciliation scan first.
            stop_when: optional predicate checked after each batch; the loop
                stops when it returns True (used by tests and bounded runs).
        """
        summary = WatchSummary()
        if startup_scan:
            summary.startup_scan = self._application.scan()
            summary.scans_triggered += 1

        started = time.monotonic()
        source = batch_source if batch_source is not None else self._watchfiles_batches()
        for batch in source:
            now = time.monotonic()
            for _change, path in batch:
                self._buffer.add(path, now)
            summary.batches_processed += 1
            self._drain(summary, now=time.monotonic())
            if stop_when is not None and stop_when():
                break
            if max_seconds is not None and time.monotonic() - started >= max_seconds:
                break

        # Source exhausted (or time limit hit): flush anything still pending.
        self._drain(summary, now=time.monotonic() + self._config.monitor.max_debounce_seconds)
        return summary

    def _drain(self, summary: WatchSummary, *, now: float) -> None:
        pending = self._buffer.ready(now)
        if pending:
            result = self._processor.process_batch(pending)
            if result.scan_triggered:
                summary.scans_triggered += 1
                _logger.info(
                    "rescanned after events on %d path(s)", len(result.relevant_paths)
                )
        reconcile_result = self._processor.maybe_reconcile()
        self._record_reconcile(summary, reconcile_result)

    def _record_reconcile(
        self, summary: WatchSummary, result: ReconcileResult
    ) -> None:
        if result.ran:
            summary.reconciliations += 1
            summary.reconciled_discrepancies += result.discrepancies
            if result.scan_triggered:
                summary.scans_triggered += 1
                _logger.info(
                    "reconciliation found %d discrepancy(ies); rescanned",
                    result.discrepancies,
                )

    def _watchfiles_batches(self) -> Iterator[set[tuple[str, str]]]:
        import watchfiles

        root = str(self._application.project_root)
        watch_filter = watchfiles.DefaultFilter(
            ignore_dirs=set(self._config.scan.excluded_directories) | {".cii"},
        )
        for batch in watchfiles.watch(
            root,
            watch_filter=watch_filter,
            debounce=200,
            rust_timeout=int(_WATCH_POLL_SECONDS * 1000),
            yield_on_timeout=True,
        ):
            yield batch
