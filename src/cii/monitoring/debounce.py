"""Event debouncing (PLAN.md §9.2).

Editor saves produce bursts of filesystem events (write, rename, chmod…).
The buffer coalesces them: a batch is ready when the project has been quiet
for ``settle_seconds``, or when events have been arriving continuously for
longer than ``max_settle_seconds`` (so a busy writer cannot starve indexing).
"""


class DebounceBuffer:
    """Coalesces filesystem event paths into settled batches."""

    def __init__(self, settle_seconds: float, max_settle_seconds: float) -> None:
        self._settle = settle_seconds
        self._max_settle = max_settle_seconds
        self._paths: set[str] = set()
        self._first_event: float | None = None
        self._last_event: float | None = None

    def add(self, path: str, now: float) -> None:
        self._paths.add(path)
        if self._first_event is None:
            self._first_event = now
        self._last_event = now

    def ready(self, now: float) -> list[str]:
        """Return and clear the pending batch when it has settled (else empty)."""
        if not self._paths or self._last_event is None or self._first_event is None:
            return []
        quiet = now - self._last_event
        held = now - self._first_event
        if quiet >= self._settle or held >= self._max_settle:
            batch = sorted(self._paths)
            self._paths.clear()
            self._first_event = None
            self._last_event = None
            return batch
        return []

    def flush(self) -> list[str]:
        """Return and clear the pending batch unconditionally."""
        batch = sorted(self._paths)
        self._paths.clear()
        self._first_event = None
        self._last_event = None
        return batch

    def __len__(self) -> int:
        return len(self._paths)
