from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from gamr_adapters.config import Settings
from gamr_core import (
    ContentOverlapResult,
    RunActivity,
    RunEvent,
    RunResult,
    RunState,
)
from pydantic import BaseModel, Field

from ..dependencies import (
    browser_safe_activity,
    get_registry,
    get_settings,
    get_task_manager,
    redaction_secrets,
)
from ..errors import browser_safe_value, conflict, not_found
from ..execution import RunTaskManager
from ..registry import InMemoryRegistry, RunRecord

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

MAX_REPLAY_NOTIFICATIONS = 1000
HEARTBEAT_SECONDS = 15
EVENT_POLL_SECONDS = 1
TERMINAL_RUN_STATES = {
    RunState.COMPLETED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.INTERRUPTED,
}
DELETABLE_RUN_STATES = TERMINAL_RUN_STATES | {RunState.QUEUED}


class ProgressItem(BaseModel):
    id: str
    label: str
    state: str
    latest_sequence: int | None = Field(default=None, alias="latestSequence")

    model_config = {"populate_by_name": True}


class CaseProgress(BaseModel):
    case_id: str = Field(alias="caseId")
    order: int
    state: str
    verdict: str | None = None
    objective_status: str | None = Field(default=None, alias="objectiveStatus")
    outcome: str | None = None
    summary: str | None = None
    assessment_status: str | None = Field(default=None, alias="assessmentStatus")
    assessment_failure: str | None = Field(default=None, alias="assessmentFailure")
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")
    missing_evidence: list[str] = Field(default_factory=list, alias="missingEvidence")
    content_overlap: ContentOverlapResult | None = Field(default=None, alias="contentOverlap")
    latest_sequence: int | None = Field(default=None, alias="latestSequence")

    model_config = {"populate_by_name": True}


class RunVisualizationSummary(BaseModel):
    id: str
    state: str
    action_mode: str = Field(alias="actionMode")
    task: str
    started_at: datetime = Field(alias="startedAt")
    latest_update_at: datetime = Field(alias="latestUpdateAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    outcome: str | None = None
    current_phase: str | None = Field(default=None, alias="currentPhase")
    current_case_ids: list[str] = Field(default_factory=list, alias="currentCaseIds")
    execution_mode: str = Field(alias="executionMode")

    model_config = {"populate_by_name": True}


class RunAttention(BaseModel):
    pending_approval_count: int = Field(alias="pendingApprovalCount")
    blockers: list[str]
    unsettled_tyr_work: bool = Field(alias="unsettledTyrWork")

    model_config = {"populate_by_name": True}


class RunCounts(BaseModel):
    total_known: bool = Field(alias="totalKnown")
    total_cases: int | None = Field(default=None, alias="totalCases")
    completed_cases: int = Field(alias="completedCases")

    model_config = {"populate_by_name": True}


class ActivityPreview(BaseModel):
    id: str
    sequence: int
    occurred_at: datetime = Field(alias="occurredAt")
    activity_type: str = Field(alias="activityType")
    status: str
    phase: str | None = None
    case_id: str | None = Field(default=None, alias="caseId")
    summary: str

    model_config = {"populate_by_name": True}


class DiscoveryField(BaseModel):
    name: str
    value: str

    model_config = {"populate_by_name": True}


class DiscoveryResult(BaseModel):
    status: str
    candidate_count: int = Field(alias="candidateCount")
    fields: list[DiscoveryField]
    reason: str | None = None

    model_config = {"populate_by_name": True}


class RunVisualization(BaseModel):
    run: RunVisualizationSummary
    phases: list[ProgressItem]
    cases: list[CaseProgress]
    attention: RunAttention
    counts: RunCounts
    latest_sequence: int = Field(alias="latestSequence")
    latest_activity: ActivityPreview | None = Field(default=None, alias="latestActivity")
    discovery_result: DiscoveryResult | None = Field(default=None, alias="discoveryResult")

    model_config = {"populate_by_name": True}


def _run_payload(run: RunRecord) -> dict[str, object]:
    return {
        "id": run.id,
        "experimentId": run.experiment_id,
        "source": run.source,
        "retryOf": run.retry_of,
        "name": run.name,
        "state": run.state,
        "task": run.task,
        "configuration": run.configuration.model_dump(by_alias=True),
        "resultPath": run.result_path,
        "createdAt": run.created_at,
        "updatedAt": run.updated_at,
        "finishedAt": run.finished_at,
    }


def _find_run(run_id: str, registry: InMemoryRegistry) -> RunRecord:
    run = registry.get_run(run_id)
    if run is None:
        raise not_found("run")
    return run


@router.get("")
def list_runs(registry: InMemoryRegistry = Depends(get_registry)) -> list[dict[str, object]]:
    runs = sorted(
        registry.runs.values(),
        key=lambda run: (run.created_at, run.updated_at, run.id),
        reverse=True,
    )
    return [_run_payload(run) for run in runs]


@router.get("/{run_id}")
def get_run(run_id: str, registry: InMemoryRegistry = Depends(get_registry)) -> dict[str, object]:
    return _run_payload(_find_run(run_id, registry))


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    manager: RunTaskManager | None = Depends(get_task_manager),
) -> dict[str, object]:
    run = _find_run(run_id, registry)
    if manager is not None:
        await manager.cancel(run_id)
        run = _find_run(run_id, registry)
    elif run.state not in TERMINAL_RUN_STATES:
        registry.set_state(run, RunState.CANCELLED, event_type="run.cancelled")
    return _run_payload(run)


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    manager: RunTaskManager | None = Depends(get_task_manager),
) -> None:
    run = _find_run(run_id, registry)
    if run.state not in DELETABLE_RUN_STATES:
        raise conflict("run_not_deletable", "run must be stopped before it can be deleted")
    if manager is not None and run.state is RunState.QUEUED:
        await manager.cancel(run_id)
    registry.delete_run(run_id)


@router.post("/{run_id}/retry", status_code=202)
async def retry_run(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    manager: RunTaskManager | None = Depends(get_task_manager),
) -> dict[str, object]:
    previous = _find_run(run_id, registry)
    if previous.source.value != "service" or previous.state not in {
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    }:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={"code": "run_not_retryable", "detail": "run cannot be retried"},
        )
    run = registry.create_run(
        previous.experiment_id,
        previous.task,
        previous.configuration,
        source=previous.source,
        retry_of=previous.id,
        name=previous.name,
    )
    if manager is not None:
        await manager.submit(run.id)
    return _run_payload(run)


@router.get("/{run_id}/events")
async def events(
    run_id: str,
    request: Request,
    last_event_id: int = Header(default=0, ge=0, alias="Last-Event-ID"),
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    run = _find_run(run_id, registry)
    follows_stream = "text/event-stream" in request.headers.get("accept", "")
    secrets = redaction_secrets(settings)

    def payload(item: object) -> dict[str, object]:
        if isinstance(item, RunActivity):
            value = browser_safe_activity(item, secrets=secrets)
            value["runId"] = run_id
            return value
        if hasattr(item, "activity_type"):
            value = browser_safe_activity(
                {
                    "id": getattr(item, "id", ""),
                    "runId": run_id,
                    "sequence": getattr(item, "sequence", 0),
                    "occurredAt": getattr(item, "occurred_at", None),
                    "activityType": getattr(item, "activity_type", "system"),
                    "status": getattr(item, "status", "unknown"),
                    "phase": getattr(item, "phase", None),
                    "caseId": getattr(item, "case_id", None),
                    "turnId": getattr(item, "turn_id", None),
                    "operationId": getattr(item, "operation_id", None),
                    "approvalId": getattr(item, "approval_id", None),
                    "sourceParticipantId": getattr(item, "source_participant_id", None),
                    "targetParticipantId": getattr(item, "target_participant_id", None),
                    "evidenceType": getattr(item, "evidence_type", "event"),
                    "summary": getattr(item, "summary", "Activity update"),
                    "evidenceRefs": getattr(item, "evidence_refs", []),
                    "detailAvailability": getattr(item, "detail_availability", "available"),
                    "sandboxEvent": getattr(item, "sandbox_event", None),
                },
                secrets=secrets,
            )
            value["runId"] = run_id
            return value
        if isinstance(item, RunEvent) or hasattr(item, "event_type"):
            event_type = getattr(item, "event_type", "run.activity")
            activity_type = (
                "run_state"
                if event_type.startswith("run.")
                else "error"
                if event_type.endswith((".failed", ".error"))
                else "system"
            )
            event_payload = getattr(item, "payload", {})
            safe_payload = browser_safe_value(event_payload, secrets)
            summary = event_type.replace(".", " ")
            if isinstance(safe_payload, dict) and isinstance(safe_payload.get("summary"), str):
                summary = safe_payload["summary"]
            return {
                "id": f"run-event-{getattr(item, 'sequence', 0)}",
                "runId": run_id,
                "sequence": getattr(item, "sequence", 0),
                "occurredAt": getattr(item, "occurred_at", None),
                "activityType": activity_type,
                "status": getattr(item, "state", "unknown"),
                "phase": safe_payload.get("phase") if isinstance(safe_payload, dict) else None,
                "caseId": safe_payload.get("caseId") if isinstance(safe_payload, dict) else None,
                "summary": summary,
                "evidenceIds": [],
                "detailAvailability": "available",
            }
        raise TypeError("unsupported run event")

    async def stream() -> AsyncIterator[str]:
        cursor = last_event_id
        last_heartbeat = time.monotonic()
        while True:
            events = sorted(registry.stream_events(run.id), key=lambda item: item.sequence)
            latest_sequence = events[-1].sequence if events else 0
            pending = [event for event in events if event.sequence > cursor]
            if cursor > latest_sequence or len(pending) > MAX_REPLAY_NOTIFICATIONS:
                resync_payload = {
                    "runId": run.id,
                    "eventType": "resync_required",
                    "reason": "replay_window_exceeded",
                    "lastEventId": cursor,
                    "latestSequence": latest_sequence,
                }
                yield f"event: resync-required\ndata: {json.dumps(resync_payload)}\n\n"
            else:
                for event in pending:
                    sequence = int(getattr(event, "sequence", 0))
                    item = payload(event)
                    item["latestSequence"] = latest_sequence
                    cursor = sequence
                    yield (
                        f"id: {sequence}\nevent: run-activity\n"
                        f"data: {json.dumps(item, default=str)}\n\n"
                    )
            if not follows_stream:
                yield f": heartbeat; interval={HEARTBEAT_SECONDS}\n\n"
                yield (
                    f"event: heartbeat\ndata: {json.dumps({'interval': HEARTBEAT_SECONDS})}\n\n"
                )
                break
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                yield f": heartbeat; interval={HEARTBEAT_SECONDS}\n\n"
                yield (
                    f"event: heartbeat\ndata: {json.dumps({'interval': HEARTBEAT_SECONDS})}\n\n"
                )
                last_heartbeat = now
            await asyncio.sleep(EVENT_POLL_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _result(run: RunRecord, settings: Settings) -> RunResult | None:
    path = Path(settings.artifact_root) / "runs" / run.id / "result.json"
    if not path.is_file():
        return None
    try:
        return RunResult.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


@router.get("/{run_id}/cases")
def cases(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    run = _find_run(run_id, registry)
    result = _result(run, settings)
    return [case.model_dump(by_alias=True, mode="json") for case in result.cases] if result else []


@router.get("/{run_id}/artifacts")
def artifacts(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    _find_run(run_id, registry)
    root = (Path(settings.artifact_root) / "runs" / run_id).resolve()
    artifact_root = Path(settings.artifact_root).resolve()
    if artifact_root not in root.parents or not root.is_dir():
        return []
    return [
        {
            "path": str(path.relative_to(root)),
            "size": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
