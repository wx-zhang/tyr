from __future__ import annotations

from collections.abc import Callable


class DiagnosticReporter:
    def __init__(self, sink: Callable[[str], None] | None = None) -> None:
        self.sink = sink
        self.seen_keys: set[str] = set()

    def report(self, stage: str, message: str, key: str | None = None) -> None:
        dedup_key = f"{stage}:{key or message}"
        if dedup_key in self.seen_keys:
            return
        self.seen_keys.add(dedup_key)
        if self.sink is not None:
            self.sink(f"[Langfuse Tracing] {stage}: {message}")
