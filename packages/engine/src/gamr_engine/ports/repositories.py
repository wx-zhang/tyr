from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from gamr_core import DatasetManifest, Scenario


class DatasetRepository(Protocol):
    def list(self) -> Sequence[DatasetManifest]: ...

    def load(self, reference: str) -> tuple[DatasetManifest, Sequence[Scenario]]: ...


class RunRepository(Protocol):
    def enqueue(self, run_id: str, dataset_id: str) -> None: ...
