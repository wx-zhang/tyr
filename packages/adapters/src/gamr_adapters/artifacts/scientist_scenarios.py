from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Literal, cast, get_args

from gamr_core import CaseResult, RunRecord, RunResult, RunState, Scenario
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_ARCHIVE_ROOT = "scientist-scenario-archive"
_SCENARIO_ROOT = "scientist-scenarios"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_-]+")
_TERMINAL_STATES = {
    RunState.COMPLETED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.INTERRUPTED,
}
CatalogState = Literal["active", "archived"]
CatalogResult = Literal[
    "vulnerable",
    "protected",
    "inconclusive",
    "not_applicable",
    "pending",
    "unavailable",
]


class ScientistScenarioNotFound(LookupError):
    pass

class ScientistScenarioArchiveMarker(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    run_id: str = Field(alias="runId")
    artifact_id: str = Field(alias="artifactId")
    scenario_id: str = Field(alias="scenarioId")
    archived_at: datetime = Field(alias="archivedAt")


@dataclass(frozen=True)
class ScientistScenarioEntry:
    artifact_id: str
    scenario: Scenario
    run_id: str
    task: str
    run_state: RunState
    run_created_at: datetime
    run_updated_at: datetime
    run_finished_at: datetime | None
    archived_at: datetime | None
    result_state: CatalogResult
    result: CaseResult | None

@dataclass(frozen=True)
class _ResolvedScenario:
    path: Path
    run: RunRecord
    scenario: Scenario
    result: CaseResult | None
    archived_at: datetime | None


class ScientistScenarioCatalog:
    _marker_locks: dict[str, RLock] = {}
    _locks_guard = RLock()

    def __init__(self, root: str | Path = ".gamr") -> None:
        self.root = Path(root).resolve()

    def list(
        self,
        *,
        state: CatalogState = "active",
        result: CatalogResult | None = None,
    ) -> list[ScientistScenarioEntry]:
        if state not in {"active", "archived"}:
            raise ValueError("scenario catalog state is invalid")
        if result is not None and result not in get_args(CatalogResult):
            raise ValueError("scenario catalog result is invalid")
        runs_root = self.root / "runs"
        if not runs_root.is_dir():
            return []
        entries: list[ScientistScenarioEntry] = []
        for run_dir in runs_root.iterdir():
            if not run_dir.is_dir():
                continue
            for artifact_path in self._scenario_paths(run_dir):
                resolved = self._resolve_path(run_dir.name, artifact_path.stem)
                if resolved is None:
                    continue
                entry = self._entry(resolved)
                if (entry.archived_at is not None) != (state == "archived"):
                    continue
                if result is not None and entry.result_state != result:
                    continue
                entries.append(entry)
        entries.sort(
            key=lambda item: (
                -item.run_created_at.timestamp(),
                item.run_id,
                item.artifact_id,
            )
        )
        return entries

    def get(self, run_id: str, artifact_id: str) -> ScientistScenarioEntry | None:
        resolved = self._resolve_path(run_id, artifact_id)
        return self._entry(resolved) if resolved is not None else None

    def archive(self, run_id: str, artifact_id: str) -> ScientistScenarioEntry:
        resolved = self._resolve_path(run_id, artifact_id)
        if resolved is None:
            raise ScientistScenarioNotFound("scientist scenario not found")
        marker_path = self._marker_path(run_id, artifact_id)
        if marker_path is None:
            raise ScientistScenarioNotFound("scientist scenario not found")
        lock = self._marker_lock(marker_path)
        with lock:
            marker = self._read_marker(marker_path)
            if marker is None or marker.scenario_id != resolved.scenario.metadata.id:
                marker = ScientistScenarioArchiveMarker(
                    runId=run_id,
                    artifactId=artifact_id,
                    scenarioId=resolved.scenario.metadata.id,
                    archivedAt=datetime.now(UTC),
                )
                marker_path.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_json(marker_path, marker.model_dump(by_alias=True, mode="json"))
        return self.get(run_id, artifact_id) or self._entry(resolved)

    def restore(self, run_id: str, artifact_id: str) -> ScientistScenarioEntry:
        resolved = self._resolve_path(run_id, artifact_id)
        if resolved is None:
            raise ScientistScenarioNotFound("scientist scenario not found")
        marker_path = self._marker_path(run_id, artifact_id)
        if marker_path is None:
            raise ScientistScenarioNotFound("scientist scenario not found")
        lock = self._marker_lock(marker_path)
        with lock:
            if self._read_marker(marker_path) is not None:
                marker_path.unlink(missing_ok=True)
        return self.get(run_id, artifact_id) or self._entry(resolved)

    def export(self, run_id: str, artifact_id: str) -> tuple[str, bytes]:
        resolved = self._resolve_path(run_id, artifact_id)
        if resolved is None:
            raise ScientistScenarioNotFound("scientist scenario not found")
        return self.safe_export_filename(resolved.scenario.metadata.id), resolved.path.read_bytes()

    def is_scientist_scenario_archived(self, run_id: str, artifact_id: str) -> bool:
        resolved = self._resolve_path(run_id, artifact_id)
        return resolved is not None and resolved.archived_at is not None

    def delete_run_markers(self, run_id: str) -> None:
        if not self._safe_id(run_id):
            raise ValueError("run identifier is invalid")
        marker_dir = self._confined(self.root / _ARCHIVE_ROOT / run_id)
        if marker_dir is not None and marker_dir.is_dir():
            shutil.rmtree(marker_dir)

    @staticmethod
    def safe_export_filename(scenario_id: str) -> str:
        safe_id = _SAFE_FILENAME.sub("-", scenario_id)[:128].strip("-") or "scenario"
        return f"{safe_id}.json"

    def _resolve_path(self, run_id: str, artifact_id: str) -> _ResolvedScenario | None:
        if not self._safe_id(run_id) or not self._safe_id(artifact_id):
            return None
        run_dir = self._confined(self.root / "runs" / run_id)
        source_dir = self._confined(run_dir / _SCENARIO_ROOT) if run_dir else None
        path = self._confined(source_dir / f"{artifact_id}.json") if source_dir else None
        if run_dir is None or source_dir is None or path is None or not path.is_file():
            return None
        run = self._read_run(run_dir)
        if run is None or run.id != run_id:
            return None
        try:
            scenario = Scenario.model_validate(self._read_json(path))
        except (OSError, ValueError, ValidationError):
            return None
        result = self._read_result(run_dir, scenario.metadata.id)
        marker = self._read_marker(self._marker_path(run_id, artifact_id))
        if marker is not None and marker.scenario_id != scenario.metadata.id:
            marker = None
        return _ResolvedScenario(
            path, run, scenario, result, marker.archived_at if marker else None
        )

    def _entry(self, resolved: _ResolvedScenario) -> ScientistScenarioEntry:
        result_state: CatalogResult = (
            cast(CatalogResult, str(resolved.result.verdict.value))
            if resolved.result is not None
            else "unavailable"
            if resolved.run.state in _TERMINAL_STATES
            else "pending"
        )
        return ScientistScenarioEntry(
            artifact_id=resolved.path.stem,
            scenario=resolved.scenario,
            run_id=resolved.run.id,
            task=resolved.run.task,
            run_state=resolved.run.state,
            run_created_at=resolved.run.created_at,
            run_updated_at=resolved.run.updated_at,
            run_finished_at=resolved.run.finished_at,
            archived_at=resolved.archived_at,
            result_state=result_state,
            result=resolved.result,
        )

    def _read_result(self, run_dir: Path, scenario_id: str) -> CaseResult | None:
        result_path = run_dir / "result.json"
        if not result_path.is_file():
            return None
        try:
            result = RunResult.model_validate(self._read_json(result_path))
        except (OSError, ValueError, ValidationError):
            return None
        if result.run_id != run_dir.name:
            return None
        return next((case for case in result.cases if case.scenario_id == scenario_id), None)

    def _read_run(self, run_dir: Path) -> RunRecord | None:
        try:
            return RunRecord.model_validate(self._read_json(run_dir / "run.json"))
        except (OSError, ValueError, ValidationError):
            return None

    def _read_marker(self, path: Path | None) -> ScientistScenarioArchiveMarker | None:
        if path is None or not path.is_file():
            return None
        try:
            marker = ScientistScenarioArchiveMarker.model_validate(self._read_json(path))
        except (OSError, ValueError, ValidationError):
            return None
        if (
            marker.schema_version != "1.0"
            or marker.run_id != path.parent.name
            or marker.artifact_id != path.stem
            or not self._safe_id(marker.run_id)
            or not self._safe_id(marker.artifact_id)
        ):
            return None
        return marker

    def _scenario_paths(self, run_dir: Path) -> Sequence[Path]:
        source_dir = self._confined(run_dir / _SCENARIO_ROOT)
        if source_dir is None or not source_dir.is_dir():
            return []
        return sorted(
            (path for path in source_dir.iterdir() if path.is_file() and path.suffix == ".json"),
            key=lambda path: path.stem,
        )

    def _marker_path(self, run_id: str, artifact_id: str) -> Path | None:
        if not self._safe_id(run_id) or not self._safe_id(artifact_id):
            return None
        return self._confined(self.root / _ARCHIVE_ROOT / run_id / f"{artifact_id}.json")

    def _confined(self, path: Path) -> Path | None:
        resolved = path.resolve()
        return resolved if self.root == resolved or self.root in resolved.parents else None

    @staticmethod
    def _safe_id(value: str) -> bool:
        return bool(_SAFE_ID.fullmatch(value))

    @classmethod
    def _marker_lock(cls, path: Path) -> RLock:
        key = str(path)
        with cls._locks_guard:
            return cls._marker_locks.setdefault(key, RLock())

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
