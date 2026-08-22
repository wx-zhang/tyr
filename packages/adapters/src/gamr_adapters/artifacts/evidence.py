from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from gamr_core import (
    ActivityType,
    Availability,
    CaseResult,
    EvidenceItem,
    EvidenceType,
    ParticipantKind,
    RunActivity,
    RunParticipant,
    RunResult,
    RunState,
)
from pydantic import ValidationError

from gamr_adapters.tyr.operations import (
    child_item_key,
    normalize_operation_result,
)

from .filesystem import FilesystemArtifactStore, redact_payload
from .query import CursorCodec

_UNSAFE_VALUE = re.compile(
    r"bearer\s+\S+|(?:api[_-]?key|token|secret)\s*[=:]\s*\S+|(?:^|[\s=:])(?:/|[A-Za-z]:[\\/]|~[/\\])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NormalizedBundle:
    activities: list[RunActivity]
    evidence: list[EvidenceItem]


@dataclass(frozen=True)
class ObservedRelationship:
    source_participant_id: str
    target_participant_id: str
    relationship_types: tuple[str, ...]
    activity_count: int
    status_counts: dict[str, int]
    first_sequence: int
    last_sequence: int


@dataclass(frozen=True)
class NormalizedRelationships:
    activities: list[RunActivity]
    participants: list[RunParticipant]
    relationships: list[ObservedRelationship]


@dataclass(frozen=True)
class NormalizedTurn:
    id: str
    sequence: int
    number: int
    stage: str
    case_id: str | None
    status: str
    agent_message: str
    tyr_message: str | None
    occurred_at: datetime | None = None
    replied_at: datetime | None = None
    update_type: str = "conversation"
    verdict: str | None = None
    objective_status: str | None = None
    outcome: str | None = None
    assessment_summary: str | None = None
    assessment_status: str | None = None
    assessment_failure: str | None = None
    reason_codes: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    content_overlap: dict[str, object] | None = None
    judge_pipeline: str | None = None
    history_case_ids: tuple[str, ...] = ()
    history_case_origins: tuple[str, ...] = ()


def _parse_occurred_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _related_case_ids(value: dict[str, object]) -> tuple[str, ...]:
    return _stored_case_ids(value.get("relatedCaseIds"))


def _stored_case_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _history_case_origins(value: dict[str, object], case_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not case_ids:
        return ()
    metadata = value.get("metadata")
    raw = metadata.get("historyOrigins") if isinstance(metadata, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return ()
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != len(case_ids):
        return ()
    return tuple("base" if part == "base" else "scientist" for part in parts)


def _activity_turn_times(bundle: Path) -> dict[str, dict[str, datetime]]:
    path = next(
        (bundle / name for name in ("activity.jsonl", "events.jsonl") if (bundle / name).is_file()),
        None,
    )
    if path is None:
        return {}
    times: dict[str, dict[str, datetime]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            turn_id = value.get("turnId")
            if not isinstance(turn_id, str) or not turn_id:
                continue
            occurred_at = _parse_occurred_at(value.get("occurredAt"))
            if occurred_at is None:
                continue
            event_type = ""
            metadata = value.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("eventType"), str):
                event_type = metadata["eventType"]
            status = str(value.get("status") or "")
            bucket = times.setdefault(turn_id, {})
            if event_type == "target.requesting" or status == "target_requesting":
                bucket.setdefault("started", occurred_at)
            elif event_type == "target.completed" or status == "target_completed":
                bucket.setdefault("replied", occurred_at)
    return times


_TURN_STAGES = frozenset({"discovery", "case", "assessment", "scientist"})


def _scientist_turns_from_activity(
    root: Path,
    *,
    run_id: str,
    secrets: Iterable[str] = (),
) -> list[NormalizedTurn]:
    path = next(
        (root / name for name in ("activity.jsonl", "events.jsonl") if (root / name).is_file()),
        None,
    )
    if path is None:
        return []
    iterations: dict[int, dict[str, object]] = {}
    open_iteration: int | None = None
    next_index = 1
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = redact_payload(json.loads(line), secrets)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            phase = value.get("phase")
            status = str(value.get("status") or "")
            metadata = value.get("metadata")
            event_type = ""
            turn_meta: int | None = None
            if isinstance(metadata, dict):
                if isinstance(metadata.get("eventType"), str):
                    event_type = metadata["eventType"]
                turn_value = metadata.get("turn")
                if isinstance(turn_value, int) and turn_value > 0:
                    turn_meta = turn_value
            if phase != "scientist" and not event_type.startswith("scientist."):
                continue
            if status in {"scientist_started", "scientist_completed"} or event_type in {
                "scientist.started",
                "scientist.completed",
            }:
                continue
            occurred_at = _parse_occurred_at(value.get("occurredAt"))
            summary = value.get("summary")
            message = str(summary).strip() if isinstance(summary, str) and summary.strip() else ""
            case_value = value.get("caseId")
            activity_case_id = (
                str(case_value) if isinstance(case_value, str) and case_value else None
            )
            if status == "model_thinking" or event_type == "model.thinking":
                if activity_case_id is None and turn_meta is not None:
                    open_iteration = turn_meta
                    next_index = max(next_index, turn_meta + 1)
                continue
            history_case_ids = _related_case_ids(value)
            history_case_origins = _history_case_origins(value, history_case_ids)
            if status == "scientist_history_used" or event_type == "scientist.history_used":
                index = turn_meta or open_iteration or next_index
                open_iteration = index
                next_index = max(next_index, index + 1)
                iterations[index] = {
                    "id": str(value.get("id") or f"{run_id}-scientist-{index}"),
                    "number": index,
                    "status": "generating",
                    "agent_message": message or "No prior tests were available.",
                    "case_id": None,
                    "occurred_at": occurred_at,
                    "history_case_ids": history_case_ids,
                    "history_case_origins": history_case_origins,
                }
                continue
            if status == "scientist_failed" or event_type == "scientist.failed":
                index = turn_meta or open_iteration or next_index
                open_iteration = None
                next_index = max(next_index, index + 1)
                previous = iterations.get(index, {})
                iterations[index] = {
                    "id": str(value.get("id") or f"{run_id}-scientist-{index}"),
                    "number": index,
                    "status": "failed",
                    "agent_message": message or f"Scientist scenario {index} failed",
                    "case_id": None,
                    "occurred_at": occurred_at,
                    "history_case_ids": previous.get("history_case_ids", ()),
                    "history_case_origins": previous.get("history_case_origins", ()),
                }
                continue
            if status == "scientist_scenario_ready" or event_type == "scientist.scenario_ready":
                index = turn_meta or open_iteration or next_index
                open_iteration = None
                next_index = max(next_index, index + 1)
                previous = iterations.get(index, {})
                iterations[index] = {
                    "id": str(value.get("id") or f"{run_id}-scientist-{index}"),
                    "number": index,
                    "status": "ready",
                    "agent_message": message or f"Scientist scenario {index} ready",
                    "case_id": activity_case_id,
                    "occurred_at": occurred_at,
                    "history_case_ids": previous.get("history_case_ids", ()),
                    "history_case_origins": previous.get("history_case_origins", ()),
                }
                continue
    result_errors = _scientist_errors_from_result(root, secrets)
    error_index = 0
    turns: list[NormalizedTurn] = []
    for _, item in sorted(iterations.items()):
        number = item["number"]
        assert isinstance(number, int)
        message = str(item["agent_message"])
        if item.get("status") == "failed" and (not message or message == "scientist failed"):
            if error_index < len(result_errors):
                message = result_errors[error_index]
                error_index += 1
            elif message == "scientist failed":
                message = f"Scientist scenario {number} failed"
        occurred_raw = item.get("occurred_at")
        history_ids = _stored_case_ids(item.get("history_case_ids", ()))
        origin_raw = item.get("history_case_origins", ())
        history_origins = (
            tuple(
                "base" if origin == "base" else "scientist"
                for origin in origin_raw
                if isinstance(origin, str)
            )
            if isinstance(origin_raw, (list, tuple))
            else ()
        )
        if len(history_origins) != len(history_ids):
            history_origins = ()
        turns.append(
            NormalizedTurn(
                id=str(item["id"]),
                sequence=0,
                number=number,
                stage="scientist",
                case_id=str(item["case_id"]) if item.get("case_id") else None,
                status=str(item["status"]),
                agent_message=message,
                tyr_message=None,
                occurred_at=occurred_raw if isinstance(occurred_raw, datetime) else None,
                replied_at=None,
                history_case_ids=history_ids,
                history_case_origins=history_origins,
            )
        )
    return turns


def _scientist_errors_from_result(root: Path, secrets: Iterable[str] = ()) -> list[str]:
    path = root / "result.json"
    if not path.is_file():
        return []
    try:
        payload = redact_payload(json.loads(path.read_text(encoding="utf-8")), secrets)
    except OSError, json.JSONDecodeError, UnicodeDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    return [
        str(error)
        for error in errors
        if isinstance(error, str) and error.startswith("scientist scenario")
    ]


def load_run_result(root: str | Path, secrets: Iterable[str] = ()) -> RunResult | None:
    path = Path(root) / "result.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = RunResult.model_validate(payload)
        safe_payload = redact_payload(
            result.model_dump(by_alias=True, exclude_none=True, mode="json"), secrets
        )
        return RunResult.model_validate(safe_payload)
    except OSError, json.JSONDecodeError, UnicodeDecodeError, ValidationError:
        return None


def _case_completion_context(root: Path) -> dict[str, tuple[str, datetime | None]]:
    path = next(
        (root / name for name in ("activity.jsonl", "events.jsonl") if (root / name).is_file()),
        None,
    )
    if path is None:
        return {}
    contexts: dict[str, tuple[str, datetime | None]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            case_id = value.get("caseId")
            if not isinstance(case_id, str) or not case_id:
                continue
            metadata = value.get("metadata")
            event_type = metadata.get("eventType") if isinstance(metadata, dict) else None
            if event_type not in {"assessment.completed", "case.completed"}:
                continue
            previous = contexts.get(case_id)
            phase = "scientist" if value.get("phase") == "scientist" else "case"
            if previous is not None and previous[0] == "scientist":
                phase = "scientist"
            occurred_at = _parse_occurred_at(value.get("occurredAt"))
            if previous is None or occurred_at is not None:
                contexts[case_id] = (phase, occurred_at)
    return contexts


def _turn_phase_rank(turn: NormalizedTurn) -> int:
    if turn.update_type == "discovery" or turn.stage == "discovery":
        return 0
    if turn.stage == "scientist" or turn.update_type == "scientist":
        return 2
    return 1


def _stamp_discovery_after_chatter(
    discovery: list[NormalizedTurn],
    conversation: list[NormalizedTurn],
) -> list[NormalizedTurn]:
    if not discovery:
        return discovery
    stamped: list[NormalizedTurn] = []
    for turn in discovery:
        if turn.occurred_at is not None:
            stamped.append(turn)
            continue
        moments: list[datetime] = []
        for item in conversation:
            if item.stage != "discovery":
                continue
            moment = item.replied_at or item.occurred_at
            if moment is not None:
                moments.append(moment)
        stamped.append(replace(turn, occurred_at=max(moments)) if moments else turn)
    return stamped


def _discovery_turn_from_artifact(
    root: Path,
    *,
    run_id: str,
    secrets: Iterable[str] = (),
) -> list[NormalizedTurn]:
    path = root / "discovery-result.json"
    if not path.is_file():
        return []
    try:
        raw = redact_payload(json.loads(path.read_text(encoding="utf-8")), secrets)
    except OSError, json.JSONDecodeError:
        return []
    if not isinstance(raw, dict):
        return []
    status = raw.get("status")
    if status not in {"found", "blocked"}:
        return []
    occurred_at = _parse_occurred_at(raw.get("occurredAt"))
    if status == "blocked":
        reason = raw.get("reason")
        message = (
            str(reason).strip()
            if isinstance(reason, str) and reason.strip()
            else "No usable discovery target."
        )
        return [
            NormalizedTurn(
                id=f"{run_id}-discovery-result",
                sequence=0,
                number=1,
                stage="discovery",
                case_id=None,
                status="blocked",
                agent_message=message,
                tyr_message=None,
                occurred_at=occurred_at,
                update_type="discovery",
            )
        ]
    raw_fields = raw.get("fields")
    lines: list[str] = []
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, str):
                lines.append(f"{name}: {value}")
    if not lines:
        return []
    return [
        NormalizedTurn(
            id=f"{run_id}-discovery-result",
            sequence=0,
            number=1,
            stage="discovery",
            case_id=None,
            status="completed",
            agent_message="\n".join(lines),
            tyr_message=None,
            occurred_at=occurred_at,
            update_type="discovery",
        )
    ]


def _evaluation_turn_from_case(
    *,
    run_id: str,
    number: int,
    case: CaseResult,
    stage: str,
    occurred_at: datetime | None,
    judge_pipeline: str | None = None,
) -> NormalizedTurn:
    return NormalizedTurn(
        id=f"{run_id}-evaluation-{case.scenario_id}",
        sequence=0,
        number=number,
        stage=stage,
        case_id=case.scenario_id,
        status=case.outcome.value,
        agent_message=case.summary,
        tyr_message=None,
        occurred_at=occurred_at,
        replied_at=None,
        update_type="evaluation",
        verdict=case.verdict.value,
        objective_status=case.objective_status.value,
        outcome=case.outcome.value,
        assessment_summary=case.summary,
        assessment_status=case.assessment_status.value,
        assessment_failure=case.assessment_failure,
        reason_codes=tuple(item.value for item in case.reason_codes),
        missing_evidence=tuple(case.missing_evidence),
        content_overlap=(
            case.content_overlap.model_dump(by_alias=True, mode="json")
            if case.content_overlap is not None
            else None
        ),
        judge_pipeline=judge_pipeline,
    )


def _evaluation_turns_from_case_results(
    root: Path,
    *,
    run_id: str,
    secrets: Iterable[str] = (),
) -> list[NormalizedTurn]:
    directory = root / "case-results"
    if not directory.is_dir():
        return []
    contexts = _case_completion_context(root)
    updates: list[NormalizedTurn] = []
    paths = sorted(directory.glob("*.json"), key=lambda path: path.name)
    for number, path in enumerate(paths, 1):
        try:
            payload = redact_payload(json.loads(path.read_text(encoding="utf-8")), secrets)
            case = CaseResult.model_validate(
                {key: value for key, value in payload.items() if key not in {"stage", "occurredAt"}}
            )
        except (
            OSError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValidationError,
            TypeError,
        ):
            continue
        stage_value = payload.get("stage") if isinstance(payload, dict) else None
        stage = (
            stage_value
            if stage_value in {"case", "scientist"}
            else contexts.get(case.scenario_id, ("case", None))[0]
        )
        occurred_raw = payload.get("occurredAt") if isinstance(payload, dict) else None
        occurred_at = _parse_occurred_at(occurred_raw)
        if occurred_at is None:
            occurred_at = contexts.get(case.scenario_id, (stage, None))[1]
        updates.append(
            _evaluation_turn_from_case(
                run_id=run_id,
                number=number,
                case=case,
                stage=stage,
                occurred_at=occurred_at,
            )
        )
    return updates


def _evaluation_turns(
    root: Path,
    *,
    run_id: str,
    secrets: Iterable[str] = (),
) -> list[NormalizedTurn]:
    result = load_run_result(root, secrets)
    if result is not None:
        contexts = _case_completion_context(root)
        updates: list[NormalizedTurn] = []
        for number, case in enumerate(result.cases, 1):
            stage, occurred_at = contexts.get(case.scenario_id, ("case", result.finished_at))
            updates.append(
                _evaluation_turn_from_case(
                    run_id=run_id,
                    number=number,
                    case=case,
                    stage=stage,
                    occurred_at=occurred_at,
                    judge_pipeline=result.judge_pipeline,
                )
            )
        return updates
    return _evaluation_turns_from_case_results(root, run_id=run_id, secrets=secrets)


def normalize_turns(
    bundle: str | Path,
    *,
    run_id: str,
    secrets: Iterable[str] = (),
) -> list[NormalizedTurn]:
    root = Path(bundle)
    path = root / "transcript.jsonl"
    activity_times = _activity_turn_times(root)
    grouped: dict[str, dict[str, object]] = {}
    context_counts: dict[tuple[str, str | None], int] = {}
    if path.is_file():
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = redact_payload(json.loads(line), secrets)
                except json.JSONDecodeError:
                    continue
                if not isinstance(value, dict):
                    continue
                turn_id = str(value.get("turnId") or f"{run_id}-turn-{line_number}")
                stage_value = value.get("stage")
                if not isinstance(stage_value, str) or stage_value not in _TURN_STAGES:
                    legacy_phase = value.get("phase")
                    stage_value = (
                        legacy_phase
                        if isinstance(legacy_phase, str) and legacy_phase in _TURN_STAGES
                        else "unknown"
                    )
                case_value = value.get("caseId")
                case_id = str(case_value) if isinstance(case_value, str) and case_value else None
                item = grouped.get(turn_id)
                occurred_at = _parse_occurred_at(value.get("occurredAt"))
                if item is None:
                    context = (stage_value, case_id)
                    context_counts[context] = context_counts.get(context, 0) + 1
                    turn_value = value.get("turn")
                    item = {
                        "id": turn_id,
                        "sequence": len(grouped) + 1,
                        "number": turn_value
                        if isinstance(turn_value, int) and turn_value > 0
                        else context_counts[context],
                        "stage": stage_value,
                        "case_id": case_id,
                        "agent_message": "",
                        "tyr_message": None,
                        "occurred_at": None,
                        "replied_at": None,
                    }
                    grouped[turn_id] = item
                content = value.get("content") or value.get("summary")
                if not isinstance(content, str) or not content.strip():
                    continue
                role = value.get("role")
                if role in {"assistant", "agent"}:
                    item["agent_message"] = content
                    if occurred_at is not None and item.get("occurred_at") is None:
                        item["occurred_at"] = occurred_at
                elif role in {"user", "tyr"}:
                    item["tyr_message"] = content
                    if occurred_at is not None and item.get("replied_at") is None:
                        item["replied_at"] = occurred_at
    conversation: list[NormalizedTurn] = []
    for item in grouped.values():
        if not item["agent_message"]:
            continue
        turn_id = str(item["id"])
        sequence = item["sequence"]
        number = item["number"]
        assert isinstance(sequence, int)
        assert isinstance(number, int)
        fallback = activity_times.get(turn_id, {})
        occurred_raw = item.get("occurred_at")
        replied_raw = item.get("replied_at")
        occurred_at = (
            occurred_raw if isinstance(occurred_raw, datetime) else fallback.get("started")
        )
        replied_at = replied_raw if isinstance(replied_raw, datetime) else fallback.get("replied")
        conversation.append(
            NormalizedTurn(
                id=turn_id,
                sequence=sequence,
                number=number,
                stage=str(item["stage"]),
                case_id=str(item["case_id"]) if item["case_id"] else None,
                status="completed" if item["tyr_message"] is not None else "waiting_for_tyr",
                agent_message=str(item["agent_message"]),
                tyr_message=str(item["tyr_message"]) if item["tyr_message"] is not None else None,
                occurred_at=occurred_at if isinstance(occurred_at, datetime) else None,
                replied_at=replied_at if isinstance(replied_at, datetime) else None,
            )
        )
    scientist = _scientist_turns_from_activity(root, run_id=run_id, secrets=secrets)
    scientist = [replace(turn, update_type="scientist") for turn in scientist]
    evaluations = _evaluation_turns(root, run_id=run_id, secrets=secrets)
    discovery = _discovery_turn_from_artifact(root, run_id=run_id, secrets=secrets)
    discovery = _stamp_discovery_after_chatter(discovery, conversation)
    combined = [*conversation, *scientist, *evaluations, *discovery]
    minimum = datetime.min.replace(tzinfo=UTC)

    def sort_key(turn: NormalizedTurn) -> tuple[int, datetime, int, str]:
        return (
            _turn_phase_rank(turn),
            turn.occurred_at or minimum,
            turn.number,
            turn.id,
        )

    ordered = sorted(combined, key=sort_key)
    return [
        NormalizedTurn(
            id=turn.id,
            sequence=index,
            number=turn.number,
            stage=turn.stage,
            case_id=turn.case_id,
            status=turn.status,
            agent_message=turn.agent_message,
            tyr_message=turn.tyr_message,
            occurred_at=turn.occurred_at,
            replied_at=turn.replied_at,
            update_type=turn.update_type,
            verdict=turn.verdict,
            objective_status=turn.objective_status,
            outcome=turn.outcome,
            assessment_summary=turn.assessment_summary,
            assessment_status=turn.assessment_status,
            assessment_failure=turn.assessment_failure,
            reason_codes=turn.reason_codes,
            missing_evidence=turn.missing_evidence,
            content_overlap=turn.content_overlap,
            judge_pipeline=turn.judge_pipeline,
            history_case_ids=turn.history_case_ids,
            history_case_origins=turn.history_case_origins,
        )
        for index, turn in enumerate(ordered, 1)
    ]


class BundleNormalizer:
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self.secrets = tuple(secret for secret in secrets if secret)

    def normalize(self, bundle: str | Path, *, run_id: str | None = None) -> list[RunActivity]:
        return self.normalize_bundle(bundle, run_id=run_id).activities

    def normalize_bundle(
        self, bundle: str | Path, *, run_id: str | None = None
    ) -> NormalizedBundle:
        root = Path(bundle)
        resolved_run_id = run_id or self._bundle_run_id(root)
        source = next(
            (root / name for name in ("activity.jsonl", "events.jsonl") if (root / name).is_file()),
            None,
        )
        activities = self._activities_from_source(source, resolved_run_id) if source else []
        if not activities:
            activities = self._from_transcript(root, resolved_run_id)
        activities = self._enrich_communication_participants(activities)
        activities = self._merge_raw_network_activities(root, resolved_run_id, activities)
        activities = self._with_terminal_run_state(root, resolved_run_id, activities)
        return NormalizedBundle(activities, self._evidence(root, resolved_run_id, activities))

    def normalize_with_relationships(
        self, bundle: str | Path, *, run_id: str | None = None
    ) -> NormalizedRelationships:
        activities = self.normalize(bundle, run_id=run_id)
        participants: dict[str, RunParticipant] = {}
        normalized: list[RunActivity] = []
        for activity in activities:
            current, observations = self._normalize_participants(activity)
            normalized.append(current)
            for participant in observations:
                existing = participants.get(participant.id)
                if existing is None or (
                    participant.first_observed_sequence < existing.first_observed_sequence
                ):
                    participants[participant.id] = participant
        return NormalizedRelationships(
            normalized, list(participants.values()), self._relationships(normalized)
        )

    def _activities_from_source(self, source: Path | None, run_id: str) -> list[RunActivity]:
        if source is None:
            return []
        parsed: list[tuple[int, int, RunActivity]] = []
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = redact_payload(json.loads(line), self.secrets)
                    activity = self._activity(record, run_id or record.get("runId"))
                    key = activity.sequence
                except json.JSONDecodeError, TypeError, ValueError, ValidationError:
                    activity = self._malformed(run_id, line_number, line)
                    key = 2**31
                parsed.append((key, line_number, activity))
        result: list[RunActivity] = []
        maximum = 0
        for _key, _line_number, activity in sorted(parsed, key=lambda item: item[:2]):
            sequence = activity.sequence if activity.sequence > maximum else maximum + 1
            result.append(activity.model_copy(update={"sequence": sequence}))
            maximum = sequence
        return result

    def _activity(self, record: object, run_id: str) -> RunActivity:
        if not isinstance(record, dict):
            raise ValueError("activity record must be an object")
        if "activityType" in record:
            allowed_fields = {
                "id",
                "runId",
                "sequence",
                "occurredAt",
                "activityType",
                "status",
                "phase",
                "caseId",
                "turnId",
                "operationId",
                "approvalId",
                "sourceParticipantId",
                "targetParticipantId",
                "evidenceType",
                "summary",
                "evidenceRefs",
                "detailAvailability",
            }
            canonical_payload = {key: record[key] for key in allowed_fields if key in record}
            canonical_payload["runId"] = run_id
            canonical_payload["metadata"] = self._participant_metadata(record, canonical_payload)
            for field in (
                "operationId",
                "approvalId",
                "sourceParticipantId",
                "targetParticipantId",
            ):
                value = canonical_payload.get(field)
                if isinstance(value, str) and _UNSAFE_VALUE.search(value):
                    canonical_payload[field] = None
            if isinstance(canonical_payload.get("status"), str) and _UNSAFE_VALUE.search(
                str(canonical_payload["status"])
            ):
                canonical_payload["status"] = "redacted"
            return RunActivity.model_validate(canonical_payload)
        event_type = str(record.get("eventType") or "system")
        payload = record.get("payload")
        details = (
            {str(key): value for key, value in payload.items()} if isinstance(payload, dict) else {}
        )
        sequence = record.get("sequence")
        if not isinstance(sequence, int) or sequence < 1:
            raise ValueError("legacy sequence is missing")
        occurred_at_value = str(record.get("occurredAt") or "1970-01-01T00:00:00Z")
        occurred_at = datetime.fromisoformat(occurred_at_value.replace("Z", "+00:00"))
        event_id = record.get("id") or self._stable_id(json.dumps(record, sort_keys=True))
        summary = details.get("summary") or details.get("detail") or event_type
        status = str(record.get("state") or self._legacy_status(event_type))
        if _UNSAFE_VALUE.search(status):
            status = "redacted"
        return RunActivity(
            id=str(event_id),
            runId=run_id,
            sequence=sequence,
            occurredAt=occurred_at,
            activityType=self._activity_type(event_type),
            status=status,
            evidenceType=EvidenceType.EVENT,
            summary=str(summary),
            detailAvailability=Availability.AVAILABLE,
        )

    @staticmethod
    def _participant_metadata(
        record: dict[str, object], payload: dict[str, object]
    ) -> dict[str, object]:
        raw_metadata = record.get("metadata")
        metadata = (
            {str(key): value for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, dict)
            else {}
        )
        for side in ("source", "target"):
            participant = record.get(f"{side}Participant")
            if not isinstance(participant, dict):
                participant = record.get(side)
            if isinstance(participant, dict):
                identifier = payload.get(f"{side}ParticipantId") or participant.get("id")
                if identifier and not payload.get(f"{side}ParticipantId"):
                    payload[f"{side}ParticipantId"] = str(identifier)
                for field, metadata_key in (
                    ("kind", "kind"),
                    ("label", "label"),
                    ("name", "label"),
                ):
                    value = participant.get(field)
                    if isinstance(value, str) and value.strip():
                        metadata[f"_{side}Participant{metadata_key.title()}"] = value.strip()
            for field, metadata_key in (("Kind", "kind"), ("Label", "label")):
                value = record.get(f"{side}Participant{field}")
                if isinstance(value, str) and value.strip():
                    metadata[f"_{side}Participant{metadata_key.title()}"] = value.strip()
        return metadata

    def _normalize_participants(
        self, activity: RunActivity
    ) -> tuple[RunActivity, list[RunParticipant]]:
        observations: list[RunParticipant] = []
        updates: dict[str, str] = {}
        for side in ("source", "target"):
            identifier = getattr(activity, f"{side}_participant_id")
            if identifier is None:
                if side == "source" and activity.target_participant_id is None:
                    continue
                identifier = f"unknown:{activity.run_id}:{activity.id}:{side}"
                updates[f"{side}_participant_id"] = identifier
            metadata = activity.metadata
            kind = self._participant_kind(metadata.get(f"_{side}ParticipantKind"))
            label = str(
                metadata.get(f"_{side}ParticipantLabel")
                or ("Unknown actor" if kind is ParticipantKind.UNKNOWN else identifier)
            )
            observations.append(
                RunParticipant(
                    id=identifier,
                    runId=activity.run_id,
                    kind=kind,
                    displayLabel=label,
                    firstObservedSequence=activity.sequence,
                    evidenceId=activity.evidence_refs[0] if activity.evidence_refs else activity.id,
                )
            )
        return (activity.model_copy(update=updates) if updates else activity), observations

    @staticmethod
    def _participant_kind(value: object) -> ParticipantKind:
        if isinstance(value, str):
            try:
                return ParticipantKind(value)
            except ValueError:
                pass
        return ParticipantKind.UNKNOWN

    @staticmethod
    def _relationships(activities: list[RunActivity]) -> list[ObservedRelationship]:
        grouped: dict[tuple[str, str], list[RunActivity]] = {}
        for activity in activities:
            if (
                activity.source_participant_id
                and activity.target_participant_id
                and activity.activity_type
                in {
                    ActivityType.COMMUNICATION,
                    ActivityType.TYR_OPERATION,
                    ActivityType.EXECUTION,
                    ActivityType.DELEGATION,
                    ActivityType.BRIDGE,
                    ActivityType.TOOL_CALL,
                    ActivityType.APPROVAL,
                }
            ):
                grouped.setdefault(
                    (activity.source_participant_id, activity.target_participant_id), []
                ).append(activity)
        relationships: list[ObservedRelationship] = []
        for (source, target), items in sorted(grouped.items()):
            types = tuple(
                dict.fromkeys(
                    BundleNormalizer._relationship_type(item.activity_type) for item in items
                )
            )
            statuses: dict[str, int] = {}
            for item in items:
                statuses[item.status] = statuses.get(item.status, 0) + 1
            relationships.append(
                ObservedRelationship(
                    source,
                    target,
                    types,
                    len(items),
                    statuses,
                    min(item.sequence for item in items),
                    max(item.sequence for item in items),
                )
            )
        return relationships

    @staticmethod
    def _relationship_type(activity_type: ActivityType) -> str:
        return {
            ActivityType.TYR_OPERATION: "operation",
            ActivityType.TOOL_CALL: "tool",
        }.get(activity_type, activity_type.value)

    def _from_transcript(self, root: Path, run_id: str) -> list[RunActivity]:
        path = root / "transcript.jsonl"
        if not path.is_file():
            return []
        result: list[RunActivity] = []
        with path.open(encoding="utf-8") as handle:
            for sequence, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = redact_payload(json.loads(line), self.secrets)
                    result.append(
                        RunActivity(
                            id=self._stable_id(f"{run_id}:transcript:{sequence}"),
                            runId=run_id,
                            sequence=sequence,
                            occurredAt=datetime(1970, 1, 1, tzinfo=UTC),
                            activityType=ActivityType.COMMUNICATION,
                            status="observed",
                            caseId=record.get("caseId"),
                            turnId=record.get("turnId"),
                            evidenceType=EvidenceType.TRANSCRIPT,
                            summary=str(
                                record.get("summary")
                                or record.get("content")
                                or "Transcript record"
                            ),
                        )
                    )
                except json.JSONDecodeError, TypeError, ValueError, ValidationError:
                    result.append(self._malformed(run_id, sequence, line))
        return result

    def _evidence(
        self, root: Path, run_id: str, activities: list[RunActivity]
    ) -> list[EvidenceItem]:
        result: list[EvidenceItem] = []
        used_refs: set[str] = set()
        result_paths: set[str] = set()
        result_path = root / "result.json"
        result_payload: dict[str, object] | None = None
        if result_path.is_file():
            try:
                value = redact_payload(
                    json.loads(result_path.read_text(encoding="utf-8")), self.secrets
                )
                result_payload = value if isinstance(value, dict) else None
            except OSError, json.JSONDecodeError:
                result.append(
                    self._item(
                        run_id,
                        "result",
                        EvidenceType.ERROR,
                        "Canonical result is malformed",
                        Availability.MALFORMED,
                    )
                )
        cases = result_payload.get("cases", []) if result_payload else []
        for case in cases if isinstance(cases, list) else []:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("scenarioId") or "unknown-case")
            for entry in case.get("evidence", []):
                if not isinstance(entry, dict):
                    continue
                relative = str(entry.get("artifact") or "")
                result_paths.add(relative)
                ref = next(
                    (
                        item
                        for activity in activities
                        if activity.case_id == case_id
                        for item in activity.evidence_refs
                        if item not in used_refs
                    ),
                    self._stable_id(f"{run_id}:artifact:{relative}"),
                )
                used_refs.add(ref)
                result.append(
                    self._artifact_item(root, run_id, ref, relative, case_id, entry.get("turnId"))
                )
        for path in sorted((root / "raw").glob("**/*")) if (root / "raw").is_dir() else []:
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in result_paths:
                continue
            result.append(
                self._artifact_item(
                    root, run_id, self._stable_id(f"{run_id}:{relative}"), relative, None, None
                )
            )
        for activity in activities:
            for reference in activity.evidence_refs:
                if reference not in used_refs:
                    result.append(
                        self._item(
                            run_id,
                            reference,
                            activity.evidence_type,
                            "Referenced evidence is not retained",
                            Availability.OMITTED,
                            activity.id,
                            {"caseId": activity.case_id} if activity.case_id else {},
                        )
                    )
                    used_refs.add(reference)
        transcript = root / "transcript.jsonl"
        if transcript.is_file():
            with transcript.open(encoding="utf-8") as handle:
                for sequence, line in enumerate(handle, 1):
                    try:
                        record = redact_payload(json.loads(line), self.secrets)
                        summary = str(
                            record.get("summary") or record.get("content") or "Transcript record"
                        )
                        availability = Availability.AVAILABLE
                    except json.JSONDecodeError, TypeError:
                        summary = "Retained transcript record is malformed"
                        availability = Availability.MALFORMED
                        record = {}
                    result.append(
                        self._item(
                            run_id,
                            self._stable_id(f"{run_id}:transcript:{sequence}"),
                            EvidenceType.TRANSCRIPT,
                            summary,
                            availability,
                            None,
                            {
                                key: str(record[key])
                                for key in ("caseId", "turnId")
                                if record.get(key)
                            },
                        )
                    )
        if result_payload is None and not result_path.is_file():
            result.append(
                self._item(
                    run_id,
                    "result",
                    EvidenceType.ARTIFACT,
                    "Canonical result is missing",
                    Availability.MISSING,
                )
            )
        return result

    def _artifact_item(
        self,
        root: Path,
        run_id: str,
        evidence_id: str,
        relative: str,
        case_id: str | None,
        turn_id: object,
    ) -> EvidenceItem:
        path = (root / relative).resolve()
        valid = root.resolve() in path.parents and path != root.resolve()
        if not valid or not path.is_file():
            availability = Availability.MISSING
            summary = "Referenced artifact is missing"
            size = None
        else:
            size = path.stat().st_size
            try:
                payload = redact_payload(json.loads(path.read_text(encoding="utf-8")), self.secrets)
                summary = str(
                    payload.get("summary")
                    if isinstance(payload, dict) and payload.get("summary")
                    else "Retained artifact"
                )
                availability = Availability.AVAILABLE
            except OSError, json.JSONDecodeError, UnicodeDecodeError:
                summary = "Retained artifact is malformed"
                availability = Availability.MALFORMED
        provenance: dict[str, str] = {}
        if case_id:
            provenance["caseId"] = case_id
        if turn_id:
            provenance["turnId"] = str(turn_id)
        return self._item(
            run_id,
            evidence_id,
            EvidenceType.DIAGNOSTIC,
            summary,
            availability,
            None,
            provenance,
            relative,
            size,
        )

    @staticmethod
    def _item(
        run_id: str,
        evidence_id: str,
        evidence_type: EvidenceType,
        summary: str,
        availability: Availability,
        activity_id: str | None = None,
        provenance: dict[str, str] | None = None,
        content_ref: str | None = None,
        content_size: int | None = None,
    ) -> EvidenceItem:
        safe_summary = summary if summary.strip() else "Evidence detail"
        if _UNSAFE_VALUE.search(safe_summary):
            safe_summary = "Evidence detail redacted"
            availability = Availability.REDACTED
        return EvidenceItem(
            id=evidence_id,
            runId=run_id,
            activityId=activity_id,
            evidenceType=evidence_type,
            summary=safe_summary[:1000],
            availability=availability,
            contentRef=content_ref,
            contentSize=content_size,
            provenance={key: value for key, value in (provenance or {}).items() if value},
        )

    @staticmethod
    def _bundle_run_id(root: Path) -> str:
        try:
            value = json.loads((root / "run.json").read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("runId"):
                return str(value["runId"])
            if isinstance(value, dict) and value.get("id"):
                return str(value["id"])
        except OSError, json.JSONDecodeError:
            pass
        return root.name

    @staticmethod
    def _terminal_state_from_run_json(root: Path) -> tuple[str, datetime] | None:
        path = root / "run.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        raw = value.get("state") or value.get("status")
        if raw == "blocked":
            raw = RunState.COMPLETED.value
        if raw not in {
            RunState.COMPLETED.value,
            RunState.FAILED.value,
            RunState.CANCELLED.value,
            RunState.INTERRUPTED.value,
        }:
            return None
        occurred = value.get("finishedAt") or value.get("updatedAt") or value.get("createdAt")
        if isinstance(occurred, str) and occurred.strip():
            try:
                occurred_at = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
            except ValueError:
                occurred_at = datetime(1970, 1, 1, tzinfo=UTC)
        else:
            occurred_at = datetime(1970, 1, 1, tzinfo=UTC)
        return str(raw), occurred_at

    def _with_terminal_run_state(
        self, root: Path, run_id: str, activities: list[RunActivity]
    ) -> list[RunActivity]:
        terminal = self._terminal_state_from_run_json(root)
        if terminal is None:
            return activities
        status, occurred_at = terminal
        if any(
            item.activity_type is ActivityType.RUN_STATE and item.status == status
            for item in activities
        ):
            return activities
        sequence = max((item.sequence for item in activities), default=0) + 1
        synthetic = RunActivity(
            id=self._stable_id(f"{run_id}:terminal:{status}"),
            runId=run_id,
            sequence=sequence,
            occurredAt=occurred_at,
            activityType=ActivityType.RUN_STATE,
            status=status,
            evidenceType=EvidenceType.EVENT,
            summary=f"Run state is {status}",
            detailAvailability=Availability.AVAILABLE,
        )
        return [*activities, synthetic]

    def _enrich_communication_participants(
        self, activities: list[RunActivity]
    ) -> list[RunActivity]:
        enriched: list[RunActivity] = []
        for activity in activities:
            if activity.source_participant_id or activity.target_participant_id:
                enriched.append(activity)
                continue
            event_type = activity.metadata.get("eventType")
            if not isinstance(event_type, str):
                enriched.append(activity)
                continue
            direction = self._communication_direction(event_type, activity.activity_type)
            if direction is None:
                enriched.append(activity)
                continue
            source, target = direction
            metadata = {
                **activity.metadata,
                "_sourceParticipantKind": "gamr" if source == "gamr" else "tyr_agent",
                "_sourceParticipantLabel": "GAMR" if source == "gamr" else "Tyr",
                "_targetParticipantKind": "tyr_agent" if target == "tyr" else "gamr",
                "_targetParticipantLabel": "Tyr" if target == "tyr" else "GAMR",
            }
            enriched.append(
                activity.model_copy(
                    update={
                        "source_participant_id": source,
                        "target_participant_id": target,
                        "metadata": metadata,
                    }
                )
            )
        return enriched

    @staticmethod
    def _communication_direction(
        event_type: str, activity_type: ActivityType
    ) -> tuple[str, str] | None:
        if event_type.startswith("target.completed") or event_type in {
            "tyr.reply",
            "target.replied",
        }:
            return "tyr", "gamr"
        if event_type.startswith(("target.", "tyr.", "model.")):
            return "gamr", "tyr"
        if activity_type in {ActivityType.COMMUNICATION, ActivityType.TYR_OPERATION}:
            if event_type.endswith(".completed") or event_type.endswith(".reply"):
                return "tyr", "gamr"
        return None

    def _merge_raw_network_activities(
        self, root: Path, run_id: str, activities: list[RunActivity]
    ) -> list[RunActivity]:
        projected = self._project_raw_network_activities(root, run_id)
        if not projected:
            return activities
        existing_ids = {item.id for item in activities}
        maximum = max((item.sequence for item in activities), default=0)
        merged = list(activities)
        for item in projected:
            if item.id in existing_ids:
                continue
            maximum += 1
            merged.append(item.model_copy(update={"sequence": maximum}))
            existing_ids.add(item.id)
        return merged

    def _project_raw_network_activities(self, root: Path, run_id: str) -> list[RunActivity]:
        raw_dir = root / "raw"
        if not raw_dir.is_dir():
            return []
        groups = (
            ("executions", ActivityType.EXECUTION, "execution"),
            ("delegations", ActivityType.DELEGATION, "delegation"),
            ("bridges", ActivityType.BRIDGE, "bridge"),
            ("toolCalls", ActivityType.TOOL_CALL, "tool call"),
            ("pendingApprovals", ActivityType.APPROVAL, "approval"),
        )
        observed: dict[tuple[str, str, str], dict[str, object]] = {}
        for path in sorted(raw_dir.glob("*.json")):
            try:
                payload = redact_payload(json.loads(path.read_text(encoding="utf-8")), self.secrets)
            except OSError, json.JSONDecodeError, TypeError, ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            result = payload.get("targetResponse")
            if not isinstance(result, dict):
                result = payload
            if not isinstance(result, dict):
                continue
            operation_id = str(
                result.get("operationId")
                or payload.get("operationId")
                or result.get("id")
                or path.stem
            )
            for group, _activity_type, _label in groups:
                entries = result.get(group)
                if not isinstance(entries, list):
                    continue
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        continue
                    item_key = child_item_key(entry, group, index)
                    observed[(operation_id, group, item_key)] = {
                        "operationId": operation_id,
                        "updatedAt": result.get("updatedAt") or payload.get("updatedAt"),
                        "entry": entry,
                        "group": group,
                    }
        if not observed:
            return []
        activities: list[RunActivity] = []
        sequence = 1
        for (operation_id, group, _item_key), record in sorted(observed.items()):
            entry = record["entry"]
            assert isinstance(entry, dict)
            partial = {
                "operationId": operation_id,
                "updatedAt": record.get("updatedAt"),
                group: [entry],
            }
            for item in normalize_operation_result(
                partial, run_id=run_id, starting_sequence=sequence
            ):
                activities.append(item)
                sequence += 1
        return activities

    @staticmethod
    def _activity_type(event_type: str) -> ActivityType:
        if event_type.startswith("run."):
            return ActivityType.RUN_STATE
        if event_type.startswith(("discovery.", "assessment.")):
            return ActivityType.PHASE
        if event_type.startswith("case."):
            return ActivityType.CASE
        if event_type.startswith(("target.", "tyr.")):
            return ActivityType.TYR_OPERATION
        if event_type.startswith("model."):
            return ActivityType.COMMUNICATION
        if event_type.endswith("error") or event_type.endswith("failed"):
            return ActivityType.ERROR
        return ActivityType.SYSTEM

    @staticmethod
    def _legacy_status(event_type: str) -> str:
        return {
            "run.started": "running",
            "run.queued": "queued",
            "run.completed": "completed",
            "run.failed": "failed",
            "run.interrupted": "interrupted",
        }.get(event_type, "observed")

    @staticmethod
    def _stable_id(value: str) -> str:
        return str(UUID(bytes=hashlib.sha256(value.encode()).digest()[:16]))

    @staticmethod
    def _malformed(run_id: str, sequence: int, source: str) -> RunActivity:
        return RunActivity(
            id=BundleNormalizer._stable_id(f"{run_id}:{sequence}:{source}"),
            runId=run_id,
            sequence=sequence,
            occurredAt=datetime(1970, 1, 1, tzinfo=UTC),
            activityType=ActivityType.ARTIFACT,
            status="malformed",
            evidenceType=EvidenceType.DIAGNOSTIC,
            summary="Retained evidence record is malformed",
            detailAvailability=Availability.MALFORMED,
        )


class FilesystemActivitySink:
    def __init__(self, store: FilesystemArtifactStore) -> None:
        self.store = store

    def append(self, activity: RunActivity) -> RunActivity:
        self.store.append_activity(activity.model_dump(by_alias=True, mode="json"))
        return activity

    def latest_sequence(self, run_id: str) -> int:
        return max(
            (int(item.get("sequence", 0)) for item in self.store.read_activity_records(run_id)),
            default=0,
        )


__all__ = [
    "BundleNormalizer",
    "FilesystemActivitySink",
    "CursorCodec",
    "NormalizedBundle",
    "NormalizedRelationships",
    "ObservedRelationship",
]
