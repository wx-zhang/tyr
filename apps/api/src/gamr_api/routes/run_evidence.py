from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from gamr_adapters.artifacts.evidence import (
    BundleNormalizer,
    NormalizedBundle,
    load_run_result,
    normalize_turns,
)
from gamr_adapters.artifacts.filesystem import (
    FilesystemArtifactStore,
    redact_payload,
)
from gamr_adapters.artifacts.query import (
    ActivityMemoryRepository,
    ActivityPage,
    RelationshipProjection,
)
from gamr_adapters.config import Settings
from gamr_core import (
    ActivityType,
    Availability,
    EvidenceItem,
    EvidenceQuery,
    EvidenceType,
    ParticipantKind,
    RunActivity,
    RunState,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..dependencies import (
    browser_safe_activity,
    browser_safe_evidence,
    get_registry,
    get_settings,
    redaction_secrets,
    require_run_evidence_access,
)
from ..errors import browser_safe_value, not_found
from ..registry import InMemoryRegistry
from .runs import RunVisualization

router = APIRouter(prefix="/api/v1/runs", tags=["run-evidence"])

_LIFECYCLE_STAGES = (
    "queued",
    "preparing",
    "discovering",
    "running",
    "scientist",
    "evaluating",
    "reporting",
)
_ACTIVITY_STAGE = {
    "discovery": "discovering",
    "case": "running",
    "execution": "running",
    "scientist": "scientist",
}
_COARSE_RUN_STATES = frozenset({"running", "waiting_for_approval"})
_CASE_STATE = {
    "case_started": "active",
    "case_completed": "completed",
    "completed": "completed",
    "active": "active",
    "running": "active",
    "failed": "failed",
    "blocked": "blocked",
    "pending": "pending",
}


class ActivityItemResponse(BaseModel):
    id: str
    sequence: int
    occurred_at: datetime = Field(alias="occurredAt")
    activity_type: str = Field(alias="activityType")
    status: str
    phase: str | None = None
    case_id: str | None = Field(default=None, alias="caseId")
    turn_id: str | None = Field(default=None, alias="turnId")
    operation_id: str | None = Field(default=None, alias="operationId")
    approval_id: str | None = Field(default=None, alias="approvalId")
    source_participant_id: str | None = Field(default=None, alias="sourceParticipantId")
    target_participant_id: str | None = Field(default=None, alias="targetParticipantId")
    evidence_type: str = Field(alias="evidenceType")
    summary: str
    evidence_ids: list[str] = Field(alias="evidenceIds")
    related_case_ids: list[str] = Field(default_factory=list, alias="relatedCaseIds")
    detail_availability: Availability = Field(alias="detailAvailability")

    model_config = ConfigDict(populate_by_name=True)


class ParticipantResponse(BaseModel):
    id: str
    kind: ParticipantKind
    display_label: str = Field(alias="displayLabel")
    first_observed_sequence: int = Field(alias="firstObservedSequence")

    model_config = ConfigDict(populate_by_name=True)


class RelationshipResponse(BaseModel):
    id: str
    source_participant_id: str = Field(alias="sourceParticipantId")
    target_participant_id: str = Field(alias="targetParticipantId")
    relationship_types: list[str] = Field(alias="relationshipTypes")
    activity_count: int = Field(alias="activityCount")
    status_counts: dict[str, int] = Field(alias="statusCounts")
    first_sequence: int = Field(alias="firstSequence")
    last_sequence: int = Field(alias="lastSequence")

    model_config = ConfigDict(populate_by_name=True)


class RelationshipProjectionResponse(BaseModel):
    participants: list[ParticipantResponse]
    relationships: list[RelationshipResponse]


class ActivityPageResponse(BaseModel):
    items: list[ActivityItemResponse]
    next_cursor: str | None = Field(alias="nextCursor")
    omitted_before: int = Field(alias="omittedBefore", ge=0)
    omitted_after: int = Field(alias="omittedAfter", ge=0)
    latest_sequence: int = Field(alias="latestSequence", ge=0)

    model_config = ConfigDict(populate_by_name=True)


class EvidenceSummaryResponse(BaseModel):
    id: str
    evidence_type: str = Field(alias="evidenceType")
    summary: str
    availability: Availability
    content_size: int | None = Field(default=None, alias="contentSize")
    download_available: bool = Field(alias="downloadAvailable")
    provenance: dict[str, str]

    model_config = ConfigDict(populate_by_name=True)


class EvidenceContentResponse(BaseModel):
    id: str
    availability: Availability
    redacted: bool = True
    content: object | None = None


class RunTurnResponse(BaseModel):
    id: str
    sequence: int
    number: int
    stage: str
    case_id: str | None = Field(default=None, alias="caseId")
    status: str
    agent_message: str = Field(alias="agentMessage")
    tyr_message: str | None = Field(default=None, alias="tyrMessage")
    occurred_at: datetime | None = Field(default=None, alias="occurredAt")
    replied_at: datetime | None = Field(default=None, alias="repliedAt")
    update_type: str = Field(default="conversation", alias="updateType")
    verdict: str | None = None
    objective_status: str | None = Field(default=None, alias="objectiveStatus")
    outcome: str | None = None
    assessment_summary: str | None = Field(default=None, alias="assessmentSummary")
    history_case_ids: list[str] = Field(default_factory=list, alias="historyCaseIds")

    model_config = ConfigDict(populate_by_name=True)


class RunTurnPageResponse(BaseModel):
    items: list[RunTurnResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    omitted_before: int = Field(alias="omittedBefore", ge=0)
    latest_sequence: int = Field(alias="latestSequence", ge=0)

    model_config = ConfigDict(populate_by_name=True)


def _bundle(run_id: str, settings: Settings) -> Path:
    root = (Path(settings.artifact_root) / "runs" / run_id).resolve()
    artifact_root = Path(settings.artifact_root).resolve()
    if artifact_root not in root.parents or not root.is_dir():
        raise not_found("run evidence")
    return root


def _normalized(
    run_id: str, settings: Settings, *, secrets: tuple[str, ...] = ()
) -> tuple[Path, NormalizedBundle]:
    root = _bundle(run_id, settings)
    return root, BundleNormalizer(secrets=secrets).normalize_bundle(root, run_id=run_id)


def _invalid_query(error: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"type": "about:blank", "code": "invalid_query", "detail": error},
    )


def _query(
    run_id: str,
    *,
    q: str | None,
    case_id: str | None,
    participant_id: str | None,
    activity_type: str | None,
    status: str | None,
    evidence_type: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    relationship_id: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> EvidenceQuery:
    if limit < 1 or limit > 200:
        raise _invalid_query("limit must be between 1 and 200")
    try:
        return EvidenceQuery(
            runId=run_id,
            q=q,
            caseId=case_id,
            participantId=participant_id,
            activityType=ActivityType(activity_type) if activity_type else None,
            status=status,
            evidenceType=EvidenceType(evidence_type) if evidence_type else None,
            occurredFrom=occurred_from,
            occurredTo=occurred_to,
            relationshipId=relationship_id,
            cursor=cursor,
            limit=limit,
        )
    except (ValidationError, ValueError) as error:
        raise _invalid_query("query parameters are invalid") from error


def _projection_payload(
    projection: RelationshipProjection, secrets: tuple[str, ...] = ()
) -> dict[str, object]:
    return {
        "participants": [
            {
                "id": browser_safe_value(participant.id, secrets),
                "kind": browser_safe_value(participant.kind.value, secrets),
                "displayLabel": browser_safe_value(participant.display_label, secrets),
                "firstObservedSequence": participant.first_observed_sequence,
            }
            for participant in projection.participants
        ],
        "relationships": [
            {
                "id": browser_safe_value(relationship.id, secrets),
                "sourceParticipantId": browser_safe_value(
                    relationship.source_participant_id, secrets
                ),
                "targetParticipantId": browser_safe_value(
                    relationship.target_participant_id, secrets
                ),
                "relationshipTypes": browser_safe_value(relationship.relationship_types, secrets),
                "activityCount": relationship.activity_count,
                "statusCounts": browser_safe_value(relationship.status_counts, secrets),
                "firstSequence": relationship.first_sequence,
                "lastSequence": relationship.last_sequence,
            }
            for relationship in projection.relationships
        ],
    }


def _activity_page_payload(
    page: ActivityPage, latest_sequence: int, secrets: tuple[str, ...] = ()
) -> ActivityPageResponse:
    return ActivityPageResponse(
        items=[
            ActivityItemResponse.model_validate(browser_safe_activity(item, secrets=secrets))
            for item in page.items
        ],
        nextCursor=page.next_cursor,
        omittedBefore=page.omitted_before,
        omittedAfter=page.omitted_after,
        latestSequence=latest_sequence,
    )


def _evidence_item(bundle: NormalizedBundle, evidence_id: str) -> EvidenceItem:
    for item in bundle.evidence:
        if item.id == evidence_id:
            return item
    raise not_found("evidence")


def _summary(item: Any, root: Path, secrets: tuple[str, ...] = ()) -> dict[str, object]:
    value = browser_safe_evidence(item, secrets=secrets)
    value["downloadAvailable"] = bool(
        item.content_ref
        and item.availability in {Availability.AVAILABLE, Availability.MALFORMED}
        and (root / item.content_ref).is_file()
    )
    return value


def _read_run_json(root: Path) -> dict[str, object]:
    try:
        value = json.loads((root / "run.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_discovery_result(
    root: Path, secrets: tuple[str, ...] = ()
) -> dict[str, object] | None:
    path = root / "discovery-result.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    if status not in {"found", "blocked"}:
        return None
    raw_fields = value.get("fields")
    fields: list[dict[str, str]] = []
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            field_value = item.get("value")
            if isinstance(name, str) and isinstance(field_value, str):
                fields.append({"name": name, "value": field_value})
    candidate_count = value.get("candidateCount", len(fields))
    if not isinstance(candidate_count, int):
        candidate_count = len(fields)
    payload: dict[str, object] = {
        "status": status,
        "candidateCount": candidate_count,
        "fields": fields,
    }
    reason = value.get("reason")
    if isinstance(reason, str) and reason:
        payload["reason"] = reason
    redacted = redact_payload(payload, secrets)
    return redacted if isinstance(redacted, dict) else payload


def _map_activity_stage(phase: str | None) -> str | None:
    if not phase:
        return None
    mapped = _ACTIVITY_STAGE.get(phase, phase)
    return mapped if mapped in _LIFECYCLE_STAGES else None


def _normalize_case_state(status: str) -> str:
    return _CASE_STATE.get(status, status if status in _CASE_STATE.values() else "unknown")


def _activity_case_state(activities: list[RunActivity]) -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
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
        item.update(
            {
                "state": _normalize_case_state(activity.status),
                "latestSequence": activity.sequence,
            }
        )
    return cases


def _activity_current_phase(activities: list[RunActivity]) -> str | None:
    for activity in reversed(activities):
        mapped = _map_activity_stage(activity.phase)
        if mapped is not None:
            return mapped
    return None


def _current_phase(
    state: str,
    metadata: dict[str, object],
    activities: list[RunActivity],
) -> str | None:
    activity_phase = _activity_current_phase(activities)
    if state in _COARSE_RUN_STATES:
        return activity_phase or "running"
    if state in _LIFECYCLE_STAGES:
        return state
    if activity_phase is not None:
        return activity_phase
    raw_phase = metadata.get("phase")
    if raw_phase:
        mapped = _map_activity_stage(str(raw_phase))
        if mapped is not None:
            return mapped
        if str(raw_phase) in _LIFECYCLE_STAGES:
            return str(raw_phase)
    if state == "completed":
        return "reporting"
    return None


def _scientist_stage_state(
    *,
    scientist_seen: bool,
    scientist_enabled: bool,
    current_index: int,
    scientist_index: int,
    terminal: bool,
    state: str,
) -> str:
    if scientist_seen:
        if current_index == scientist_index:
            return state if terminal else "active"
        if state == "completed" or current_index > scientist_index:
            return "completed"
        return "pending"
    if scientist_enabled and not terminal and current_index < scientist_index:
        return "pending"
    return "skipped"


def _lifecycle_progress(
    state: str,
    metadata: dict[str, object],
    activities: list[RunActivity],
    *,
    scientist_enabled: bool = False,
) -> tuple[list[dict[str, object]], str | None]:
    current = _current_phase(state, metadata, activities)
    current_index = _LIFECYCLE_STAGES.index(current) if current in _LIFECYCLE_STAGES else -1
    terminal = state in {"completed", "failed", "cancelled", "interrupted"}
    scientist_index = _LIFECYCLE_STAGES.index("scientist")
    scientist_seen = any(
        _map_activity_stage(activity.phase) == "scientist" for activity in activities
    )
    result: list[dict[str, object]] = []
    for index, stage in enumerate(_LIFECYCLE_STAGES):
        if stage == "scientist":
            stage_state = _scientist_stage_state(
                scientist_seen=scientist_seen,
                scientist_enabled=scientist_enabled or scientist_seen,
                current_index=current_index,
                scientist_index=scientist_index,
                terminal=terminal,
                state=state,
            )
        elif state == "completed" or index < current_index:
            stage_state = "completed"
        elif index == current_index:
            stage_state = state if terminal else "active"
        else:
            stage_state = "pending"
        latest = max(
            (
                activity.sequence
                for activity in activities
                if _map_activity_stage(activity.phase) == stage
            ),
            default=None,
        )
        result.append(
            {
                "id": stage,
                "label": stage.replace("_", " ").title(),
                "state": stage_state,
                "latestSequence": latest,
            }
        )
    return result, current


@router.get("/{run_id}/visualization", response_model=RunVisualization)
def visualization(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    run = require_run_evidence_access(run_id, registry)
    artifact_root = Path(settings.artifact_root).resolve()
    bundle_root = (artifact_root / "runs" / run_id).resolve()
    if artifact_root not in bundle_root.parents or not bundle_root.is_dir():
        snapshot = registry.progress_snapshot(run_id)
        if snapshot is None:
            raise not_found("run")
        return cast(dict[str, object], browser_safe_value(snapshot, redaction_secrets(settings)))
    secrets = redaction_secrets(settings)
    root, bundle = _normalized(run_id, settings, secrets=secrets)
    metadata = _read_run_json(root)
    state = str(metadata.get("state") or metadata.get("status") or run.state.value)
    if state == "blocked":
        state = RunState.COMPLETED.value
    cases = _activity_case_state(bundle.activities)
    result = load_run_result(root, secrets)
    if result is not None:
        for case in result.cases:
            item = cases.setdefault(
                case.scenario_id,
                {
                    "caseId": case.scenario_id,
                    "order": len(cases),
                    "latestSequence": None,
                },
            )
            item.update(
                {
                    "state": case.outcome.value,
                    "verdict": case.verdict.value,
                    "objectiveStatus": case.objective_status.value,
                    "outcome": case.outcome.value,
                    "summary": case.summary,
                }
            )
    known_cases = metadata.get("caseIds") or run.configuration.case_ids or list(cases)
    for order, case_id in enumerate(known_cases if isinstance(known_cases, list) else [], 0):
        cases.setdefault(
            str(case_id),
            {
                "caseId": str(case_id),
                "order": order,
                "state": "unknown",
                "verdict": None,
                "latestSequence": None,
            },
        )
    scientist_enabled = run.configuration.scientist_iterations > 0
    config_meta = metadata.get("configuration")
    if isinstance(config_meta, dict):
        iterations = config_meta.get("scientistIterations", config_meta.get("scientist_iterations"))
        if isinstance(iterations, int):
            scientist_enabled = iterations > 0
    phases, current_phase = _lifecycle_progress(
        state,
        metadata,
        bundle.activities,
        scientist_enabled=scientist_enabled,
    )
    pending_approvals = sum(
        activity.activity_type is ActivityType.APPROVAL and activity.status == "pending"
        for activity in bundle.activities
    )
    blockers = [
        activity.summary
        for activity in bundle.activities
        if activity.status in {"failed", "interrupted", "blocked"}
        or activity.status.endswith("_failed")
    ]
    unsettled = any(
        activity.activity_type.value in {"delegation", "bridge", "execution"}
        and activity.status in {"pending", "running"}
        for activity in bundle.activities
    )
    latest_update = (
        metadata.get("latestUpdateAt")
        or metadata.get("updatedAt")
        or run.updated_at
        or run.created_at
    )
    current_case_ids = [
        str(item["caseId"])
        for item in cases.values()
        if item["state"] in {"active", "blocked", "running"}
    ]
    execution_mode = (
        "scientist_only"
        if run.configuration.case_ids == [] and run.configuration.scientist_iterations > 0
        else "cases"
    )
    payload = cast(
        dict[str, object],
        browser_safe_value(
            {
                "run": {
                    "id": run_id,
                    "state": state,
                    "actionMode": metadata.get("actionMode") or run.configuration.action_mode,
                    "dataset": metadata.get("dataset") or run.dataset,
                    "startedAt": metadata.get("startedAt") or run.created_at,
                    "latestUpdateAt": latest_update,
                    "finishedAt": metadata.get("finishedAt"),
                    "outcome": state if state in {item.value for item in RunState} else None,
                    "currentPhase": current_phase,
                    "currentCaseIds": current_case_ids,
                    "executionMode": execution_mode,
                },
                "phases": phases,
                "cases": sorted(cases.values(), key=lambda item: int(str(item["order"]))),
                "attention": {
                    "pendingApprovalCount": pending_approvals,
                    "blockers": blockers,
                    "unsettledTyrWork": unsettled,
                },
                "counts": {
                    "totalKnown": isinstance(known_cases, list),
                    "totalCases": len(known_cases) if isinstance(known_cases, list) else None,
                    "completedCases": sum(
                        item["state"] == "completed" for item in cases.values()
                    ),
                },
                "latestSequence": max((item.sequence for item in bundle.activities), default=0),
            },
            secrets,
        ),
    )
    discovery_result = _load_discovery_result(root, secrets)
    if discovery_result is not None:
        payload["discoveryResult"] = discovery_result
    return payload


@router.get("/{run_id}/turns", response_model=RunTurnPageResponse)
def turns(
    run_id: str,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> RunTurnPageResponse:
    run = require_run_evidence_access(run_id, registry)
    root = _bundle(run_id, settings)
    secrets = redaction_secrets(settings)
    normalized = normalize_turns(root, run_id=run_id, secrets=secrets)
    latest_sequence = normalized[-1].sequence if normalized else 0
    candidates = [item for item in normalized if cursor is None or item.sequence < cursor]
    page = candidates[-limit:]
    omitted_before = len(candidates) - len(page)
    terminal = run.state in {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    }
    items = [
        RunTurnResponse(
            id=item.id,
            sequence=item.sequence,
            number=item.number,
            stage=item.stage,
            caseId=item.case_id,
            status=(
                "incomplete" if terminal and item.status == "waiting_for_tyr" else item.status
            ),
            agentMessage=item.agent_message,
            tyrMessage=item.tyr_message,
            occurredAt=item.occurred_at,
            repliedAt=item.replied_at,
            updateType=item.update_type,
            verdict=item.verdict,
            objectiveStatus=item.objective_status,
            outcome=item.outcome,
            assessmentSummary=item.assessment_summary,
            historyCaseIds=list(item.history_case_ids),
        )
        for item in page
    ]
    return RunTurnPageResponse(
        items=items,
        nextCursor=str(page[0].sequence) if omitted_before and page else None,
        omittedBefore=omitted_before,
        latestSequence=latest_sequence,
    )


@router.get("/{run_id}/relationships", response_model=RelationshipProjectionResponse)
def relationships(
    run_id: str,
    q: str | None = Query(default=None),
    case_id: str | None = Query(default=None, alias="caseId"),
    participant_id: str | None = Query(default=None, alias="participantId"),
    activity_type: str | None = Query(default=None, alias="activityType"),
    status: str | None = None,
    evidence_type: str | None = Query(default=None, alias="evidenceType"),
    occurred_from: datetime | None = Query(default=None, alias="occurredFrom"),
    occurred_to: datetime | None = Query(default=None, alias="occurredTo"),
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_run_evidence_access(run_id, registry)
    try:
        query = _query(
            run_id,
            q=q,
            case_id=case_id,
            participant_id=participant_id,
            activity_type=activity_type,
            status=status,
            evidence_type=evidence_type,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        _root, bundle = _normalized(
            run_id, settings, secrets=redaction_secrets(settings)
        )
        result = ActivityMemoryRepository(bundle.activities).aggregate_relationships(query)
        return _projection_payload(result, redaction_secrets(settings))
    except ValueError as error:
        raise _invalid_query(str(error)) from error


@router.get("/{run_id}/activity", response_model=ActivityPageResponse)
def activity(
    run_id: str,
    q: str | None = Query(default=None),
    case_id: str | None = Query(default=None, alias="caseId"),
    participant_id: str | None = Query(default=None, alias="participantId"),
    activity_type: str | None = Query(default=None, alias="activityType"),
    status: str | None = None,
    evidence_type: str | None = Query(default=None, alias="evidenceType"),
    occurred_from: datetime | None = Query(default=None, alias="occurredFrom"),
    occurred_to: datetime | None = Query(default=None, alias="occurredTo"),
    relationship_id: str | None = Query(default=None, alias="relationshipId"),
    cursor: str | None = None,
    limit: int = 100,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> ActivityPageResponse:
    require_run_evidence_access(run_id, registry)
    secrets = redaction_secrets(settings)
    evidence_query = _query(
        run_id,
        q=q,
        case_id=case_id,
        participant_id=participant_id,
        activity_type=activity_type,
        status=status,
        evidence_type=evidence_type,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        relationship_id=relationship_id,
        cursor=cursor,
        limit=limit,
    )
    if relationship_id:
        pass
    _root, bundle = _normalized(run_id, settings, secrets=secrets)
    try:
        repository = ActivityMemoryRepository(bundle.activities)
        page = repository.query(evidence_query)
    except ValueError as error:
        raise _invalid_query(str(error)) from error
    return ActivityPageResponse(
        items=[
            ActivityItemResponse.model_validate(
                browser_safe_activity(item, secrets=secrets)
            )
            for item in page.items
        ],
        nextCursor=page.next_cursor,
        omittedBefore=page.omitted_before,
        omittedAfter=page.omitted_after,
        latestSequence=page.latest_sequence,
    )


@router.get("/{run_id}/evidence/{evidence_id}", response_model=EvidenceSummaryResponse)
def evidence_summary(
    run_id: str,
    evidence_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_run_evidence_access(run_id, registry)
    secrets = redaction_secrets(settings)
    root, bundle = _normalized(run_id, settings, secrets=secrets)
    item = _evidence_item(bundle, evidence_id)
    return _summary(item, root, secrets)


@router.get("/{run_id}/evidence/{evidence_id}/content", response_model=EvidenceContentResponse)
def evidence_content(
    run_id: str,
    evidence_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_run_evidence_access(run_id, registry)
    secrets = redaction_secrets(settings)
    root, bundle = _normalized(run_id, settings, secrets=secrets)
    item = _evidence_item(bundle, evidence_id)
    response: dict[str, object] = {
        "id": item.id,
        "availability": item.availability,
        "redacted": True,
        "content": None,
    }
    if (
        item.availability not in {Availability.AVAILABLE, Availability.REDACTED}
        or not item.content_ref
    ):
        return response
    try:
        content = FilesystemArtifactStore(
            settings.artifact_root, secrets=secrets
        ).read_evidence_content(
            run_id, item.content_ref
        )
    except OverflowError as error:
        raise HTTPException(
            status_code=413, detail={"code": "evidence_too_large", "detail": str(error)}
        ) from error
    except FileNotFoundError as error:
        raise not_found("evidence") from error
    except ValueError:
        response["availability"] = Availability.MALFORMED
        return response
    response["content"] = browser_safe_value(content, secrets)
    return response


@router.get("/{run_id}/evidence/{evidence_id}/download")
def evidence_download(
    run_id: str,
    evidence_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_run_evidence_access(run_id, registry)
    secrets = redaction_secrets(settings)
    _root, bundle = _normalized(run_id, settings, secrets=secrets)
    item = _evidence_item(bundle, evidence_id)
    if (
        item.availability
        not in {Availability.AVAILABLE, Availability.REDACTED, Availability.MALFORMED}
        or not item.content_ref
    ):
        raise not_found("evidence content")
    try:
        content = FilesystemArtifactStore(
            settings.artifact_root, secrets=secrets
        ).read_evidence_download(
            run_id, item.content_ref
        )
    except (FileNotFoundError, ValueError) as error:
        raise not_found("evidence content") from error
    filename = FilesystemArtifactStore.safe_evidence_filename(run_id, evidence_id)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
