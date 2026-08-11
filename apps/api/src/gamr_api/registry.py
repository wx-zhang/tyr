from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from gamr_adapters.artifacts.evidence import BundleNormalizer
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_core import (
    ActivityType,
    EvidenceType,
    ExperimentConfig,
    RunActivity,
    RunEvent,
    RunSource,
    RunState,
    transition,
)
from gamr_core import (
    ExperimentRecord as ExperimentDocument,
)
from gamr_core import (
    RunRecord as RunDocument,
)
from gamr_core.identifiers import new_id

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class ExperimentRecord:
    id: str
    name: str
    dataset: str
    configuration: ExperimentConfig = field(default_factory=ExperimentConfig)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RunRecord:
    id: str
    experiment_id: str | None
    dataset: str
    state: RunState = RunState.QUEUED
    configuration: ExperimentConfig = field(default_factory=ExperimentConfig)
    result_path: str | None = None
    events: list[RunEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    source: RunSource = RunSource.SERVICE
    retry_of: str | None = None
    error_summary: str | None = None
    name: str | None = None


@dataclass
class InMemoryRegistry:
    experiments: dict[str, ExperimentRecord] = field(default_factory=dict)
    runs: dict[str, RunRecord] = field(default_factory=dict)
    activities: dict[str, list[RunActivity]] = field(default_factory=dict)
    case_runs: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def create_experiment(
        self, name: str, dataset: str, configuration: ExperimentConfig | None = None
    ) -> ExperimentRecord:
        item = ExperimentRecord(new_id(), name, dataset, configuration or ExperimentConfig())
        self.experiments[item.id] = item
        return item

    def create_run(
        self,
        experiment_id: str | None,
        dataset: str,
        configuration: ExperimentConfig | None = None,
        *,
        source: RunSource = RunSource.SERVICE,
        retry_of: str | None = None,
        name: str | None = None,
    ) -> RunRecord:
        now = datetime.now(UTC)
        item = RunRecord(
            new_id(),
            experiment_id,
            dataset,
            configuration=configuration or ExperimentConfig(),
            created_at=now,
            updated_at=now,
            source=source,
            retry_of=retry_of,
            name=name,
        )
        self.runs[item.id] = item
        self.append_event(item, "run.queued", {"dataset": dataset})
        return item

    def get_run(self, run_id: str) -> RunRecord | None:
        _validate_id(run_id)
        return self.runs.get(run_id)

    def set_state(
        self,
        run: RunRecord,
        target: RunState,
        *,
        event_type: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        if run.state != target:
            run.state = transition(run.state, target)
        now = datetime.now(UTC)
        run.updated_at = now
        run.error_summary = error_summary
        if target in {
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.INTERRUPTED,
        }:
            run.finished_at = now
        self.append_event(run, event_type or f"run.{target.value}", {})

    def set_result(self, run: RunRecord, result_path: str) -> None:
        run.result_path = result_path
        run.updated_at = datetime.now(UTC)

    def save_run(self, run: RunRecord) -> None:
        self.runs[run.id] = run

    def delete_run(self, run_id: str) -> None:
        _validate_id(run_id)
        self.runs.pop(run_id, None)
        self.activities.pop(run_id, None)
        self.case_runs.pop(run_id, None)

    def append_event(
        self, run: RunRecord, event_type: str, payload: dict[str, object]
    ) -> RunEvent:
        event = RunEvent(
            sequence=len(run.events) + 1,
            run_id=run.id,
            event_type=event_type,
            state=run.state.value,
            occurred_at=datetime.now(UTC),
            payload=payload,
        )
        run.events.append(event)
        return event

    def refresh(self) -> None:
        return None

    def stream_events(
        self, run_id: str, after_sequence: int = 0
    ) -> list[RunActivity | RunEvent]:
        activities = self.activities.get(run_id)
        if activities:
            return [item for item in activities if item.sequence > after_sequence]
        run = self.runs.get(run_id)
        return [item for item in run.events if item.sequence > after_sequence] if run else []

    def progress_snapshot(self, run_id: str) -> dict[str, object] | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        activities = sorted(self.activities.get(run_id, []), key=lambda item: item.sequence)
        cases: dict[str, dict[str, object]] = {}
        for order, item in enumerate(self.case_runs.get(run_id, [])):
            case_id = str(item.get("caseId") or item.get("scenarioId") or "")
            if case_id:
                cases[case_id] = {
                    "caseId": case_id,
                    "order": item.get("order", order),
                    "state": item.get("status", "unknown"),
                    "verdict": item.get("verdict"),
                    "latestSequence": None,
                }
        for activity in activities:
            if not activity.case_id:
                continue
            item = cases.setdefault(
                activity.case_id,
                {
                    "caseId": activity.case_id,
                    "order": len(cases),
                    "state": "unknown",
                    "verdict": None,
                    "latestSequence": None,
                },
            )
            item.update({"state": activity.status, "latestSequence": activity.sequence})
        current_cases = [
            str(item["caseId"])
            for item in cases.values()
            if item["state"] in {"active", "blocked", "running"}
        ]
        phase_names = (
            "queued",
            "preparing",
            "discovering",
            "running",
            "scientist",
            "evaluating",
            "reporting",
        )
        stage_map = {
            "discovery": "discovering",
            "case": "running",
            "execution": "running",
            "scientist": "scientist",
        }
        coarse_states = {RunState.RUNNING, RunState.WAITING_FOR_APPROVAL}
        activity_phase: str | None = None
        for activity in reversed(activities):
            if not activity.phase:
                continue
            mapped = stage_map.get(activity.phase, activity.phase)
            if mapped in phase_names:
                activity_phase = mapped
                break
        if run.state in coarse_states:
            current_phase: str | None = activity_phase or "running"
        elif run.state.value in phase_names:
            current_phase = run.state.value
        else:
            current_phase = activity_phase
        phases = []
        current_index = phase_names.index(current_phase) if current_phase in phase_names else -1
        scientist_index = phase_names.index("scientist")
        scientist_seen = any(
            stage_map.get(item.phase or "", item.phase) == "scientist" for item in activities
        )
        scientist_enabled = run.configuration.scientist_iterations > 0 or scientist_seen
        terminal = run.state in {
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.INTERRUPTED,
        }
        for index, phase in enumerate(phase_names):
            if phase == "scientist" and not scientist_seen:
                if scientist_enabled and not terminal and current_index < scientist_index:
                    state = "pending"
                else:
                    state = "skipped"
            elif run.state is RunState.COMPLETED or index < current_index:
                state = "completed"
            elif index == current_index:
                state = run.state.value if run.state in {
                    RunState.FAILED,
                    RunState.CANCELLED,
                    RunState.INTERRUPTED,
                } else "active"
            else:
                state = "pending"
            if phase == "scientist" and scientist_seen:
                if current_index == scientist_index:
                    state = run.state.value if terminal else "active"
                elif run.state is RunState.COMPLETED or current_index > scientist_index:
                    state = "completed"
            phases.append(
                {
                    "id": phase,
                    "label": phase.replace("_", " ").title(),
                    "state": state,
                    "latestSequence": max(
                        (
                            item.sequence
                            for item in activities
                            if stage_map.get(item.phase or "", item.phase) == phase
                        ),
                        default=None,
                    ),
                }
            )
        blockers = [
            item.summary
            for item in activities
            if item.status in {"blocked", "pending", "failed", "interrupted"}
        ]
        pending_approvals = sum(
            item.activity_type.value == "approval" and item.status == "pending"
            for item in activities
        )
        unsettled = any(
            item.activity_type.value in {"tyr_operation", "execution", "delegation", "bridge"}
            and item.status in {"pending", "running", "active"}
            for item in activities
        )
        latest_sequence = max(
            [len(run.events), *(item.sequence for item in activities)], default=0
        )
        completed_cases = sum(item["state"] == "completed" for item in cases.values())
        latest = activities[-1] if activities else None
        return {
            "run": {
                "id": run.id,
                "state": run.state.value,
                "actionMode": run.configuration.action_mode,
                "dataset": run.dataset,
                "startedAt": run.created_at,
                "latestUpdateAt": run.updated_at,
                "finishedAt": run.finished_at,
                "outcome": run.state.value if run.finished_at else None,
                "currentPhase": current_phase,
                "currentCaseIds": current_cases,
                "executionMode": (
                    "scientist_only"
                    if run.configuration.case_ids == []
                    and run.configuration.scientist_iterations > 0
                    else "cases"
                ),
            },
            "phases": phases,
            "cases": sorted(cases.values(), key=lambda item: int(str(item["order"]))),
            "attention": {
                "pendingApprovalCount": pending_approvals,
                "blockers": blockers,
                "unsettledTyrWork": unsettled,
            },
            "counts": {
                "totalKnown": bool(self.case_runs.get(run_id)),
                "totalCases": len(cases) if self.case_runs.get(run_id) else None,
                "completedCases": completed_cases,
            },
            "latestSequence": latest_sequence,
            "latestActivity": (
                {
                    "id": latest.id,
                    "sequence": latest.sequence,
                    "occurredAt": latest.occurred_at,
                    "activityType": latest.activity_type.value,
                    "status": latest.status,
                    "phase": latest.phase,
                    "caseId": latest.case_id,
                    "summary": latest.summary,
                }
                if latest
                else None
            ),
        }


class JsonRegistry(InMemoryRegistry):
    def __init__(self, root: str | Path = ".gamr", *, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.root = Path(root)
        self.secrets = tuple(secret for secret in secrets if secret)
        self.store = FilesystemArtifactStore(self.root, secrets=self.secrets)
        self.refresh()

    def refresh(self) -> None:
        self.experiments = {}
        self.runs = {}
        experiments_root = self.root / "experiments"
        if experiments_root.is_dir():
            for path in sorted(experiments_root.glob("*.json")):
                try:
                    document = ExperimentDocument.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError):
                    continue
                self.experiments[document.id] = ExperimentRecord(
                    document.id,
                    document.name,
                    document.dataset,
                    document.configuration,
                    document.created_at,
                )
        runs_root = self.root / "runs"
        if runs_root.is_dir():
            for path in sorted(runs_root.glob("*/run.json")):
                item = self._load_run(path)
                if item is not None:
                    self.runs[item.id] = item

    def create_experiment(
        self, name: str, dataset: str, configuration: ExperimentConfig | None = None
    ) -> ExperimentRecord:
        item = super().create_experiment(name, dataset, configuration)
        self.store.write_json(
            f"experiments/{item.id}.json",
            ExperimentDocument(
                id=item.id,
                name=item.name,
                dataset=item.dataset,
                configuration=item.configuration,
                createdAt=item.created_at,
            ).model_dump(by_alias=True, mode="json"),
        )
        return item

    def create_run(
        self,
        experiment_id: str | None,
        dataset: str,
        configuration: ExperimentConfig | None = None,
        *,
        source: RunSource = RunSource.SERVICE,
        retry_of: str | None = None,
        name: str | None = None,
    ) -> RunRecord:
        item = super().create_run(
            experiment_id,
            dataset,
            configuration,
            source=source,
            retry_of=retry_of,
            name=name,
        )
        self._persist_run(item)
        self._persist_event(item.events[-1])
        return item

    def get_run(self, run_id: str) -> RunRecord | None:
        _validate_id(run_id)
        path = self.root / "runs" / run_id / "run.json"
        item = self._load_run(path) if path.is_file() else None
        if item is not None:
            self.runs[run_id] = item
        return item

    def set_state(
        self,
        run: RunRecord,
        target: RunState,
        *,
        event_type: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        super().set_state(run, target, event_type=event_type, error_summary=error_summary)
        self._persist_run(run)

    def set_result(self, run: RunRecord, result_path: str) -> None:
        super().set_result(run, result_path)
        self._persist_run(run)

    def save_run(self, run: RunRecord) -> None:
        super().save_run(run)
        self._persist_run(run)

    def delete_run(self, run_id: str) -> None:
        _validate_id(run_id)
        self.store.delete_run(run_id)
        super().delete_run(run_id)

    def append_event(
        self, run: RunRecord, event_type: str, payload: dict[str, object]
    ) -> RunEvent:
        event = super().append_event(run, event_type, payload)
        if (self.root / "runs" / run.id / "run.json").is_file():
            self._persist_event(event)
        return event

    def interrupt_service_runs(self) -> list[str]:
        interrupted: list[str] = []
        for run in list(self.runs.values()):
            if run.source is RunSource.SERVICE and run.state not in {
                RunState.COMPLETED,
                RunState.FAILED,
                RunState.CANCELLED,
                RunState.INTERRUPTED,
            }:
                self.set_state(run, RunState.INTERRUPTED, event_type="run.interrupted")
                interrupted.append(run.id)
        return interrupted

    def stream_events(
        self, run_id: str, after_sequence: int = 0
    ) -> list[RunActivity | RunEvent]:
        run = self.get_run(run_id)
        if run is None:
            return []
        bundle = self.root / "runs" / run_id
        activities = BundleNormalizer(secrets=self.secrets).normalize(bundle, run_id=run_id)
        if activities:
            return [item for item in activities if item.sequence > after_sequence]
        return [item for item in run.events if item.sequence > after_sequence]

    def _persist_run(self, run: RunRecord) -> None:
        result_path = run.result_path
        if result_path:
            try:
                result_path = Path(result_path).resolve().relative_to(
                    (self.root / "runs" / run.id).resolve()
                ).as_posix()
            except ValueError:
                result_path = None
        document = RunDocument(
            id=run.id,
            source=run.source,
            experimentId=run.experiment_id,
            retryOf=run.retry_of,
            name=run.name,
            dataset=run.dataset,
            state=run.state,
            configuration=run.configuration,
            resultPath=result_path,
            errorSummary=run.error_summary,
            createdAt=run.created_at,
            updatedAt=run.updated_at,
            finishedAt=run.finished_at,
        )
        self.store.write_json(
            f"runs/{run.id}/run.json", document.model_dump(by_alias=True, mode="json")
        )

    def _persist_event(self, event: RunEvent) -> None:
        self.store.append_event(
            event.run_id,
            event.model_dump(by_alias=True, mode="json"),
        )
        if event.event_type.startswith("run."):
            sequence = max(
                (
                    int(item.get("sequence", 0))
                    for item in self.store.read_activity_records(event.run_id)
                ),
                default=0,
            )
            self.store.append_activity(
                RunActivity(
                    id=new_id(),
                    runId=event.run_id,
                    sequence=sequence + 1,
                    occurredAt=event.occurred_at,
                    activityType=ActivityType.RUN_STATE,
                    status=event.state,
                    evidenceType=EvidenceType.EVENT,
                    summary=f"Run state is {event.state}",
                ).model_dump(by_alias=True, mode="json")
            )

    def _load_run(self, path: Path) -> RunRecord | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            document = RunDocument.model_validate(value)
        except (OSError, ValueError):
            return self._load_legacy_run(path)
        result_path = (
            str(path.parent / document.result_path) if document.result_path else None
        )
        return RunRecord(
            id=document.id,
            experiment_id=document.experiment_id,
            name=document.name,
            dataset=document.dataset,
            state=document.state,
            configuration=document.configuration,
            result_path=result_path,
            events=self._load_events(path.parent, document.id),
            created_at=document.created_at,
            updated_at=document.updated_at,
            finished_at=document.finished_at,
            source=document.source,
            retry_of=document.retry_of,
            error_summary=document.error_summary,
        )

    def _load_legacy_run(self, path: Path) -> RunRecord | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            run_id = str(value.get("runId") or path.parent.name)
            status = str(value.get("status") or "interrupted")
            legacy_state = {
                "blocked": RunState.COMPLETED,
                "error": RunState.FAILED,
            }.get(status)
            state = legacy_state or RunState(status)
            created_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        except (OSError, ValueError, AttributeError):
            return None
        result = path.parent / "result.json"
        return RunRecord(
            run_id,
            None,
            str(value.get("dataset") or "unknown"),
            state,
            ExperimentConfig.model_validate(value.get("configuration") or {}),
            str(result) if result.is_file() else None,
            self._load_events(path.parent, run_id),
            created_at,
            created_at,
            created_at if state in {RunState.COMPLETED, RunState.FAILED} else None,
            RunSource.CLI,
        )

    @staticmethod
    def _load_events(bundle: Path, run_id: str) -> list[RunEvent]:
        path = bundle / "events.jsonl"
        if not path.is_file():
            return []
        events: list[RunEvent] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    events.append(RunEvent.model_validate_json(line))
                except ValueError:
                    continue
        return [event for event in events if event.run_id == run_id]


def _validate_id(identifier: str) -> None:
    if not _SAFE_ID.fullmatch(identifier):
        raise ValueError("identifier is invalid")
