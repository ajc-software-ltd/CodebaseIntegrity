"""Tests for event debouncing."""

from cii.monitoring.debounce import DebounceBuffer


class TestDebounceBuffer:
    def test_empty_not_ready(self) -> None:
        buffer = DebounceBuffer(settle_seconds=1.0, max_settle_seconds=5.0)
        assert buffer.ready(10.0) == []

    def test_settles_after_quiet_period(self) -> None:
        buffer = DebounceBuffer(settle_seconds=1.0, max_settle_seconds=5.0)
        buffer.add("a.py", now=0.0)
        buffer.add("b.py", now=0.2)
        assert buffer.ready(0.9) == []  # still settling
        assert buffer.ready(1.3) == ["a.py", "b.py"]
        assert buffer.ready(2.0) == []  # cleared

    def test_batch_is_sorted_and_deduplicated(self) -> None:
        buffer = DebounceBuffer(settle_seconds=1.0, max_settle_seconds=5.0)
        buffer.add("b.py", now=0.0)
        buffer.add("a.py", now=0.0)
        buffer.add("b.py", now=0.1)
        assert buffer.ready(2.0) == ["a.py", "b.py"]

    def test_max_settle_forces_emission_under_continuous_events(self) -> None:
        buffer = DebounceBuffer(settle_seconds=1.0, max_settle_seconds=5.0)
        for tick in range(5):
            buffer.add(f"f{tick}.py", now=float(tick))  # events every second
            assert buffer.ready(float(tick)) == []  # never quiet, under max hold
        buffer.add("f5.py", now=5.0)
        # held for max_settle_seconds despite continuous events → emit now
        assert buffer.ready(5.0) == [f"f{i}.py" for i in range(6)]

    def test_flush_returns_everything(self) -> None:
        buffer = DebounceBuffer(settle_seconds=1.0, max_settle_seconds=5.0)
        buffer.add("a.py", now=0.0)
        assert buffer.flush() == ["a.py"]
        assert len(buffer) == 0
