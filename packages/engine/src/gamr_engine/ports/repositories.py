from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from gamr_core import Scenario, TaskManifest


class TaskRepository(Protocol):
    def list(self) -> Sequence[TaskManifest]: ...

    def load(self, reference: str) -> tuple[TaskManifest, Sequence[Scenario]]: ...


class RunRepository(Protocol):
    def enqueue(self, run_id: str, task_id: str) -> None: ...
