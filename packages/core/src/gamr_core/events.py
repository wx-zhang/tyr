from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .sandbox import SandboxOperationEvent
from .states import RunState

ActivityId = str
RunId = str
ParticipantId = str
EvidenceId = str


class ActivityType(StrEnum):
    RUN_STATE = "run_state"
    PHASE = "phase"
    CASE = "case"
    COMMUNICATION = "communication"
    TYR_OPERATION = "tyr_operation"
    EXECUTION = "execution"
    DELEGATION = "delegation"
    BRIDGE = "bridge"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    FINDING = "finding"
    ARTIFACT = "artifact"
    ERROR = "error"
    SYSTEM = "system"


class EvidenceType(StrEnum):
    EVENT = "event"
    TRANSCRIPT = "transcript"
    DIAGNOSTIC = "diagnostic"
    APPROVAL = "approval"
    FINDING = "finding"
    ARTIFACT = "artifact"
    ERROR = "error"


class Availability(StrEnum):
    AVAILABLE = "available"
    REDACTED = "redacted"
    OMITTED = "omitted"
    MISSING = "missing"
    MALFORMED = "malformed"


class ParticipantKind(StrEnum):
    HUMAN = "human"
    GAMR = "gamr"
    MODEL_AGENT = "model_agent"
    TYR_AGENT = "tyr_agent"
    DELEGATED_AGENT = "delegated_agent"
    BRIDGE = "bridge"
    TOOL = "tool"
    UNKNOWN = "unknown"


def _safe_text(value: str, *, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _safe_metadata(value: Mapping[str, object]) -> dict[str, object]:
    if len(value) > 32:
        raise ValueError("metadata has too many fields")
    for key, item in value.items():
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError("metadata values must be scalar")
        if isinstance(item, str):
            _safe_text(item, field_name=f"metadata.{key}")
    return dict(value)


class RunActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ActivityId = Field(min_length=1)
    run_id: RunId = Field(alias="runId", min_length=1)
    sequence: int = Field(gt=0)
    occurred_at: datetime = Field(alias="occurredAt")
    activity_type: ActivityType = Field(alias="activityType")
    status: str = Field(min_length=1, max_length=100)
    phase: str | None = Field(default=None, min_length=1)
    case_id: str | None = Field(default=None, alias="caseId", min_length=1)
    turn_id: str | None = Field(default=None, alias="turnId", min_length=1)
    operation_id: str | None = Field(default=None, alias="operationId", min_length=1)
    approval_id: str | None = Field(default=None, alias="approvalId", min_length=1)
    source_participant_id: ParticipantId | None = Field(
        default=None, alias="sourceParticipantId", min_length=1
    )
    target_participant_id: ParticipantId | None = Field(
        default=None, alias="targetParticipantId", min_length=1
    )
    evidence_type: EvidenceType = Field(alias="evidenceType")
    summary: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[EvidenceId] = Field(default_factory=list, alias="evidenceRefs")
    related_case_ids: list[str] = Field(default_factory=list, alias="relatedCaseIds")
    detail_availability: Availability = Field(
        default=Availability.AVAILABLE, alias="detailAvailability"
    )
    metadata: dict[str, object] = Field(default_factory=dict)
    sandbox_event: SandboxOperationEvent | None = Field(default=None, alias="sandboxEvent")

    @field_validator("occurred_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        offset = value.utcoffset()
        if value.tzinfo is None or offset is None or offset.total_seconds() != 0:
            raise ValueError("occurredAt must be an explicit UTC timestamp")
        return value

    @field_validator("summary")
    @classmethod
    def safe_summary(cls, value: str) -> str:
        return _safe_text(value, field_name="summary")

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return _safe_metadata(value)

    @field_validator("evidence_refs")
    @classmethod
    def unique_evidence_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("evidenceRefs must be unique")
        for item in value:
            _safe_text(item, field_name="evidenceRefs")
        return value

    @field_validator("related_case_ids")
    @classmethod
    def unique_related_case_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("relatedCaseIds must be unique")
        if len(value) > 100:
            raise ValueError("relatedCaseIds must contain at most 100 items")
        for item in value:
            _safe_text(item, field_name="relatedCaseIds")
        return value

    @model_validator(mode="after")
    def validate_state_activity(self) -> RunActivity:
        if self.activity_type is ActivityType.RUN_STATE:
            try:
                RunState(self.status)
            except ValueError as error:
                raise ValueError("run_state status must be a RunState value") from error
        return self


class RunParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: ParticipantId = Field(min_length=1)
    run_id: RunId = Field(alias="runId", min_length=1)
    kind: ParticipantKind
    display_label: str = Field(alias="displayLabel", min_length=1, max_length=200)
    first_observed_sequence: int = Field(alias="firstObservedSequence", gt=0)
    evidence_id: EvidenceId = Field(alias="evidenceId", min_length=1)

    @field_validator("display_label")
    @classmethod
    def safe_display_label(cls, value: str) -> str:
        return _safe_text(value, field_name="displayLabel")


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: EvidenceId = Field(min_length=1)
    run_id: RunId = Field(alias="runId", min_length=1)
    activity_id: ActivityId | None = Field(default=None, alias="activityId", min_length=1)
    evidence_type: EvidenceType = Field(alias="evidenceType")
    summary: str = Field(min_length=1, max_length=1000)
    availability: Availability
    content_ref: str | None = Field(default=None, alias="contentRef", min_length=1)
    content_size: int | None = Field(default=None, alias="contentSize", ge=0)
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("summary")
    @classmethod
    def safe_summary(cls, value: str) -> str:
        return _safe_text(value, field_name="summary")

    @field_validator("provenance")
    @classmethod
    def safe_provenance(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: str(item) for key, item in _safe_metadata(value).items()}


class EvidenceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: RunId = Field(alias="runId", min_length=1)
    query: str | None = Field(default=None, alias="q", max_length=200, min_length=1)
    case_id: str | None = Field(default=None, alias="caseId")
    participant_id: ParticipantId | None = Field(default=None, alias="participantId")
    activity_type: ActivityType | None = Field(default=None, alias="activityType")
    status: str | None = None
    evidence_type: EvidenceType | None = Field(default=None, alias="evidenceType")
    occurred_from: datetime | None = Field(default=None, alias="occurredFrom")
    occurred_to: datetime | None = Field(default=None, alias="occurredTo")
    relationship_id: str | None = Field(default=None, alias="relationshipId")
    cursor: str | None = None
    order: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=100, ge=1, le=200)

    @field_validator("occurred_from", "occurred_to")
    @classmethod
    def utc_filter(cls, value: datetime | None) -> datetime | None:
        offset = value.utcoffset() if value is not None else None
        if value is not None and (
            value.tzinfo is None or offset is None or offset.total_seconds() != 0
        ):
            raise ValueError("query timestamps must be explicit UTC timestamps")
        return value

    @property
    def q(self) -> str | None:
        return self.query


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    run_id: str
    event_type: str
    state: str
    occurred_at: datetime
    payload: dict[str, object] = Field(default_factory=dict)
