"""Watcher loop tests (synthetic event source + one live watchfiles run)."""

from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.database.database import Database
from cii.database.repositories import ProjectRepository, SymbolRepository
from cii.monitoring.watcher import ProjectWatcher


@pytest.fixture
def application(project_root: Path):
    config = CiiConfig.defaults()
    database = Database.open(project_root)
    ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    yield Application(project_root, config, database)
    database.close()


class TestWatcherWithSyntheticSource:
    def test_startup_scan_runs_first(self, application) -> None:
        (application.project_root / "a.py").write_text("class A:\n    pass\n")
        watcher = ProjectWatcher(application, application.config)
        summary = watcher.run(batch_source=iter([]))
        assert summary.startup_scan is not None
        assert summary.startup_scan.scan.changes.added[0].relative_path == "a.py"
        assert summary.scans_triggered == 1

    def test_event_batches_trigger_rescans(self, application) -> None:
        root = application.project_root
        watcher = ProjectWatcher(application, application.config)
        batches = iter([
            set(),  # warm-up/timeout batch
            {("added", str(root / "a.py"))},
            {("modified", str(root / "a.py"))},
        ])
        (root / "a.py").write_text("class A:\n    pass\n")
        summary = watcher.run(batch_source=batches, startup_scan=False)
        assert summary.batches_processed == 3
        assert summary.scans_triggered >= 1
        rows = SymbolRepository(application.database.connection).list_by_name("A")
        assert rows, "file changed during the watch run must end up indexed"

    def test_temporary_events_do_not_scan(self, application) -> None:
        root = application.project_root
        watcher = ProjectWatcher(application, application.config)
        batches = iter([{("added", str(root / "a.py~"))}])
        summary = watcher.run(batch_source=batches, startup_scan=False)
        assert summary.scans_triggered == 0

    def test_max_seconds_stops_run(self, application) -> None:
        root = application.project_root

        def endless():
            while True:
                yield {("modified", str(root / "a.py"))}

        watcher = ProjectWatcher(application, application.config)
        summary = watcher.run(batch_source=endless(), startup_scan=False, max_seconds=0.3)
        assert summary.batches_processed >= 1


@pytest.mark.integration
class TestLiveWatcher:
    def test_filesystem_change_reflected_automatically(self, application) -> None:
        """Live inotify run: a file written during the watch run is indexed
        without any explicit scan call (PLAN.md §21 M07 acceptance)."""
        import threading
        import time

        root = application.project_root
        symbols = SymbolRepository(application.database.connection)

        def writer() -> None:
            time.sleep(0.7)  # brief pause so the watch is established
            (root / "live.py").write_text("class Live:\n    pass\n")

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        watcher = ProjectWatcher(application, application.config)
        summary = watcher.run(
            startup_scan=False,
            max_seconds=20.0,
            stop_when=lambda: bool(symbols.list_by_name("Live")),
        )
        thread.join(timeout=5.0)
        assert symbols.list_by_name("Live"), "file written during watch was not indexed"
        assert summary.scans_triggered >= 1
