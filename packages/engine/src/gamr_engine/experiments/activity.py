from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gamr_core import (
    ActivityType,
    EvidenceType,
    RunActivity,
    RunState,
    SandboxOperationEvent,
)
from gamr_core.identifiers import new_id

from ..ports.artifacts import ActivitySink
from .records import ProgressCallback, ProgressEvent


class RunEvents:
    def __init__(
        self,
        progress: ProgressCallback | None,
        activity_sink: ActivitySink | None,
    ) -> None:
        self._progress = progress
        self._activity_sink = activity_sink
        self._activity_sequences: dict[str, int] = {}
        self._scenario_execution_ids: dict[tuple[str, str], str] = {}

    def begin_run(self, run_id: str, activity_sink: ActivitySink | None) -> None:
        self._activity_sink = activity_sink or self._activity_sink
        self._activity_sequences.pop(run_id, None)

    def register_execution(self, run_id: str, scenario_id: str, execution_id: str) -> None:
        self._scenario_execution_ids[(run_id, scenario_id)] = execution_id

    def emit(
        self,
        event_type: str,
        run_id: str,
        *,
        phase: str | None = None,
        case_id: str | None = None,
        scenario_execution_id: str | None = None,
        turn: int | None = None,
        turn_id: str | None = None,
        detail: str | None = None,
        fields: tuple[tuple[str, str], ...] | None = None,
        related_case_ids: tuple[str, ...] = (),
        metadata_extra: dict[str, object] | None = None,
        evidence_refs: tuple[str, ...] | list[str] = (),
        operation_id: str | None = None,
        sandbox_event: SandboxOperationEvent | None = None,
    ) -> None:
        sink = self._activity_sink
        if sink is not None:
            sequence = self._activity_sequences.get(run_id)
            if sequence is None:
                latest_sequence = getattr(sink, "latest_sequence", None)
                sequence = (latest_sequence(run_id) if callable(latest_sequence) else 0) + 1
            else:
                sequence += 1
            self._activity_sequences[run_id] = sequence
            try:
                activity_kind = activity_type(event_type)
                source, target, participant_meta = activity_participants(event_type)
                metadata: dict[str, object] = (
                    {"eventType": event_type, "turn": turn}
                    if turn is not None
                    else {"eventType": event_type}
                )
                metadata.update(participant_meta)
                if metadata_extra:
                    metadata.update(metadata_extra)
                execution_id = scenario_execution_id or (
                    self._scenario_execution_ids.get((run_id, case_id))
                    if case_id is not None
                    else None
                )
                activity_fields: dict[str, Any] = dict(
                    id=new_id(),
                    runId=run_id,
                    sequence=sequence,
                    occurredAt=datetime.now(UTC),
                    activityType=activity_kind,
                    status=activity_status(event_type),
                    phase=phase,
                    scenarioId=case_id,
                    scenarioExecutionId=execution_id,
                    turnId=turn_id,
                    sourceParticipantId=source,
                    targetParticipantId=target,
                    evidenceType=(
                        EvidenceType.FINDING
                        if event_type.startswith("assessment.")
                        else EvidenceType.EVENT
                    ),
                    relatedScenarioExecutionIds=list(related_case_ids),
                    evidenceRefs=list(evidence_refs),
                    metadata=metadata,
                    operationId=operation_id,
                    sandboxEvent=sandbox_event,
                )
                activity = RunActivity(
                    summary=activity_summary(event_type, detail), **activity_fields
                )
                sink.append(activity)
            except ValueError:
                self._activity_sequences.pop(run_id, None)
                raise
        if self._progress is not None:
            self._progress(
                ProgressEvent(
                    event_type,
                    run_id,
                    phase=phase,
                    case_id=case_id,
                    scenario_id=case_id,
                    scenario_execution_id=scenario_execution_id
                    or (
                        self._scenario_execution_ids.get((run_id, case_id))
                        if case_id is not None
                        else None
                    ),
                    turn=turn,
                    detail=detail,
                    fields=fields,
                    history_case_ids=related_case_ids,
                )
            )


def activity_type(event_type: str) -> ActivityType:
    if event_type.startswith("run."):
        return ActivityType.RUN_STATE
    if event_type.startswith(("discovery.", "scientist.")):
        return (
            ActivityType.ERROR
            if event_type.endswith((".failed", ".skipped"))
            else ActivityType.PHASE
        )
    if event_type.startswith("case."):
        return ActivityType.CASE
    if event_type.startswith("assessment."):
        return ActivityType.FINDING
    if event_type.startswith(("model.",)):
        return ActivityType.COMMUNICATION
    if event_type.startswith(("target.", "tyr.")):
        return ActivityType.ERROR if event_type.endswith(".failed") else ActivityType.TYR_OPERATION
    if event_type.startswith("sandbox."):
        return ActivityType.EXECUTION
    if event_type.startswith("turn."):
        return ActivityType.EXECUTION
    if event_type.endswith(".failed") or event_type.endswith(".error"):
        return ActivityType.ERROR
    return ActivityType.SYSTEM


def activity_participants(
    event_type: str,
) -> tuple[str | None, str | None, dict[str, object]]:
    if event_type.startswith("target.completed") or event_type in {
        "tyr.reply",
        "target.replied",
    }:
        return (
            "tyr",
            "gamr",
            {
                "_sourceParticipantKind": "tyr_agent",
                "_sourceParticipantLabel": "Tyr",
                "_targetParticipantKind": "gamr",
                "_targetParticipantLabel": "GAMR",
            },
        )
    if event_type.startswith(("target.", "tyr.", "model.")):
        return (
            "gamr",
            "tyr",
            {
                "_sourceParticipantKind": "gamr",
                "_sourceParticipantLabel": "GAMR",
                "_targetParticipantKind": "tyr_agent",
                "_targetParticipantLabel": "Tyr",
            },
        )
    return None, None, {}


def activity_status(event_type: str) -> str:
    if event_type == "run.started":
        return "running"
    if event_type.startswith("run."):
        status = event_type.removeprefix("run.")
        return status if status in {state.value for state in RunState} else "running"
    return event_type.replace(".", "_")


def activity_summary(event_type: str, detail: str | None) -> str:
    if not detail:
        return event_type.replace(".", " ")
    if event_type.startswith("scientist."):
        return detail[:1000]
    if not any(marker in detail.lower() for marker in ("bearer", "/", "\\")):
        return detail[:1000]
    return event_type.replace(".", " ")
