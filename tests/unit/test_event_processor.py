"""Tests for event filtering, incremental rescanning, and reconciliation."""

import time
from pathlib import Path

import pytest

from cii.application import Application
from cii.core.configuration import CiiConfig
from cii.database.database import Database
from cii.database.repositories import ProjectRepository
from cii.monitoring.event_processor import EventProcessor, is_temporary_path


@pytest.fixture
def application(project_root: Path):
    config = CiiConfig.defaults()
    database = Database.open(project_root)
    ProjectRepository(database.connection).register(
        "demo", str(project_root), "1.0", "hash"
    )
    yield Application(project_root, config, database)
    database.close()


class TestTemporaryPaths:
    @pytest.mark.parametrize("name", [
        "main.py~", "main.py.swp", "main.py.tmp", ".#main.py", "main.py.part",
    ])
    def test_temporary(self, name: str) -> None:
        assert is_temporary_path(name) is True

    @pytest.mark.parametrize("name", ["main.py", "main.cpp", "README.md"])
    def test_real_source(self, name: str) -> None:
        assert is_temporary_path(name) is False


class TestProcessBatch:
    def test_ignores_temporary_and_outside_paths(self, application) -> None:
        processor = EventProcessor(application, application.config)
        result = processor.process_batch([
            "main.py~",
            str(application.project_root.parent / "elsewhere.py"),
        ])
        assert result.scan_triggered is False
        assert result.relevant_paths == []

    def test_triggers_incremental_scan_for_relevant_paths(self, application) -> None:
        (application.project_root / "a.py").write_text("x = 1\n")
        processor = EventProcessor(application, application.config)
        result = processor.process_batch([
            str(application.project_root / "a.py"),
            "a.py.swp",
        ])
        assert result.scan_triggered is True
        assert len(result.relevant_paths) == 1
        assert result.scan is not None
        assert result.scan.index.files_indexed == 1

    def test_deletion_events_are_relevant(self, application) -> None:
        (application.project_root / "a.py").write_text("x = 1\n")
        application.scan()
        (application.project_root / "a.py").unlink()
        processor = EventProcessor(application, application.config)
        result = processor.process_batch([str(application.project_root / "a.py")])
        assert result.scan_triggered is True
        assert result.scan.scan.changes.deleted == ["a.py"]


class TestReconciliation:
    def test_not_due_does_nothing(self, application) -> None:
        processor = EventProcessor(application, application.config)
        result = processor.maybe_reconcile(now=time.monotonic())
        assert result.ran is False

    def test_due_without_discrepancies(self, application) -> None:
        (application.project_root / "a.py").write_text("x = 1\n")
        application.scan()
        config = application.config
        processor = EventProcessor(application, config)
        future = time.monotonic() + config.monitor.reconcile_interval_seconds + 1
        result = processor.maybe_reconcile(now=future)
        assert result.ran is True
        assert result.discrepancies == 0
        assert result.scan_triggered is False

    def test_due_with_missed_event_rescans(self, application) -> None:
        (application.project_root / "a.py").write_text("x = 1\n")
        application.scan()
        # a file appears without any watcher event (missed event)
        (application.project_root / "missed.py").write_text("y = 2\n")
        config = application.config
        processor = EventProcessor(application, config)
        future = time.monotonic() + config.monitor.reconcile_interval_seconds + 1
        result = processor.maybe_reconcile(now=future)
        assert result.ran is True
        assert result.discrepancies == 1
        assert result.scan_triggered is True
        assert result.scan.scan.changes.added[0].relative_path == "missed.py"

    def test_interval_reschedules(self, application) -> None:
        config = application.config
        processor = EventProcessor(application, config)
        first = time.monotonic() + config.monitor.reconcile_interval_seconds + 1
        assert processor.maybe_reconcile(now=first).ran is True
        assert processor.maybe_reconcile(now=first + 1).ran is False
