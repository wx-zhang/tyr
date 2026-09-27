from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .states import AssessmentReasonCode, ObjectiveStatus, SecurityVerdict


class DiscoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = Field(default=None, min_length=1)
    workspace: str = Field(min_length=1)
    agent: str | None = Field(default=None, min_length=1)
    bridge_id: str = Field(alias="bridgeId", min_length=1)
    bridge_status: str = Field(default="active", alias="bridgeStatus", min_length=1)
    evidence_turn_ids: list[str] = Field(default_factory=list, alias="evidenceTurnIds")

    @model_validator(mode="after")
    def validate_scope(self) -> DiscoveryCandidate:
        if self.bridge_status != "active":
            raise ValueError("discovery candidates require an active Bridge")
        return self


class TargetOrigin(StrEnum):
    PROVIDED = "provided"
    LIVE = "live"
    FALLBACK_LIVE = "fallback-live"


class DiscoveryInputCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: str | None = Field(default=None, min_length=1)
    workspace: str = Field(min_length=1)
    agent: str | None = Field(default=None, min_length=1)
    bridge_id: str = Field(alias="bridgeId", min_length=1)


class DiscoveryInputDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    kind: Literal["discovery-input"]
    task_id: str = Field(alias="taskId", min_length=1)
    candidate: DiscoveryInputCandidate


class NextTurnDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["send", "phase_complete", "phase_blocked"]
    message: str | None = None
    reason: str | None = None
    discovered_candidates: list[DiscoveryCandidate] = Field(
        default_factory=list, alias="discoveredCandidates"
    )

    @model_validator(mode="after")
    def validate_kind(self) -> NextTurnDecision:
        if self.kind == "send" and not self.message:
            raise ValueError("send decisions require a message")
        if self.kind != "send" and not self.reason:
            raise ValueError("terminal decisions require a reason")
        return self


class ScenarioExecutionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    objective_status: ObjectiveStatus = Field(alias="objectiveStatus")
    verdict: SecurityVerdict
    summary: str = Field(min_length=1)
    evidence_turn_ids: list[str] = Field(alias="evidenceTurnIds")
    reason_codes: list[AssessmentReasonCode] = Field(default_factory=list, alias="reasonCodes")
    missing_evidence: list[str] = Field(default_factory=list, alias="missingEvidence")


CaseAssessment = ScenarioExecutionAssessment
