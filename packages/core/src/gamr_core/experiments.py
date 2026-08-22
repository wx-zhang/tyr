from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .states import (
    AssessmentReasonCode,
    AssessmentStatus,
    ContentMatchType,
    ContentOverlapStatus,
    DecodingFailureCode,
    DecodingStatus,
    ExecutionOutcome,
    ObjectiveStatus,
    RunState,
    SecurityVerdict,
)


class RunSource(StrEnum):
    CLI = "cli"
    SERVICE = "service"


class TaskReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    digest: str


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action_mode: str = Field(
        default="read_only", alias="actionMode", pattern=r"^(read_only|approval_required)$"
    )
    model: str = ""
    scientist_model: str = Field(default="", alias="scientistModel")
    judge_model: str = Field(default="", alias="judgeModel")
    max_turns: int = Field(default=40, alias="maxTurns", ge=1)
    discovery_turns: int = Field(default=20, alias="discoveryTurns", ge=1)
    case_ids: list[str] | None = Field(default=None, alias="caseIds")
    scientist_iterations: int = Field(default=0, alias="scientistIterations", ge=0)
    history_test_runs: int = Field(default=10, alias="historyTestRuns", ge=0, le=100)
    history_scientist_runs: int = Field(default=5, alias="historyScientistRuns", ge=0, le=100)
    max_concurrent_cases: int = Field(default=5, alias="maxConcurrentCases", ge=1, le=5)

    @model_validator(mode="after")
    def require_execution_work(self) -> ExperimentConfig:
        if self.case_ids == [] and self.scientist_iterations == 0:
            raise ValueError(
                "select at least one case or enable scientist iterations for execution"
            )
        return self


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    configuration: ExperimentConfig = Field(default_factory=ExperimentConfig)
    created_at: datetime = Field(alias="createdAt")


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    source: RunSource
    experiment_id: str | None = Field(default=None, alias="experimentId")
    retry_of: str | None = Field(default=None, alias="retryOf")
    name: str | None = Field(default=None)
    task: str = Field(min_length=1)
    state: RunState
    configuration: ExperimentConfig = Field(default_factory=ExperimentConfig)
    result_path: str | None = Field(default=None, alias="resultPath")
    error_summary: str | None = Field(default=None, alias="errorSummary")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")

    @field_validator("result_path")
    @classmethod
    def relative_result_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("resultPath must be a confined relative path")
        return value


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(alias="turnId")
    artifact: str


class CheckedContentFile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    file_id: str = Field(alias="fileId", min_length=1)
    filename: str = Field(min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContentMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reference_item_id: str = Field(alias="referenceItemId", pattern=r"^ref-[0-9]{4}$")
    uploaded_item_id: str = Field(alias="uploadedItemId", min_length=1)
    match_type: ContentMatchType = Field(alias="matchType")


class DerivedContentFile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_file_id: str = Field(alias="sourceFileId", min_length=1)
    uploaded_item_id: str = Field(alias="uploadedItemId", min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    detected_content_type: str = Field(alias="detectedContentType", min_length=1)


class DecodingLimitFlags(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    timed_out: bool = Field(default=False, alias="timedOut")
    output_limited: bool = Field(default=False, alias="outputLimited")


class DecodingProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: DecodingStatus
    attempt_count: int = Field(default=0, alias="attemptCount", ge=0, le=3)
    failure_code: DecodingFailureCode | None = Field(default=None, alias="failureCode")
    program_sha256: list[str] = Field(
        default_factory=list,
        alias="programSha256",
    )
    limit_flags: DecodingLimitFlags = Field(
        default_factory=DecodingLimitFlags, alias="limitFlags"
    )
    derived_files: list[DerivedContentFile] = Field(
        default_factory=list, alias="derivedFiles"
    )

    @field_validator("program_sha256")
    @classmethod
    def validate_program_digests(cls, digests: list[str]) -> list[str]:
        import re

        pattern = re.compile(r"^[0-9a-f]{64}$")
        for digest in digests:
            if not pattern.match(digest):
                raise ValueError(f"invalid program SHA-256 digest: {digest}")
        return digests

    @model_validator(mode="after")
    def validate_provenance_consistency(self) -> DecodingProvenance:
        if len(self.program_sha256) != self.attempt_count:
            raise ValueError("programSha256 count must equal attemptCount")
        return self


class ContentOverlapResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: ContentOverlapStatus
    assessment_status: AssessmentStatus = Field(alias="assessmentStatus")
    failure: str | None = None
    summary: str | None = Field(default=None, max_length=600)
    full_summary: str | None = Field(default=None, alias="fullSummary")
    reference_sha256: str | None = Field(
        default=None, alias="referenceSha256", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    checked_files: list[CheckedContentFile] = Field(default_factory=list, alias="checkedFiles")
    matches: list[ContentMatch] = Field(default_factory=list)
    decoding: DecodingProvenance | None = None

    @model_validator(mode="after")
    def validate_matches(self) -> ContentOverlapResult:
        if self.status is ContentOverlapStatus.CONFIRMED and not self.matches:
            raise ValueError("confirmed content overlap requires a match")
        if self.status is not ContentOverlapStatus.CONFIRMED and self.matches:
            raise ValueError("only confirmed content overlap may contain matches")
        return self


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId")
    outcome: ExecutionOutcome
    objective_status: ObjectiveStatus = Field(
        default=ObjectiveStatus.UNKNOWN, alias="objectiveStatus"
    )
    verdict: SecurityVerdict
    summary: str
    evidence: list[Evidence]
    assessment_status: AssessmentStatus = Field(
        default=AssessmentStatus.UNKNOWN, alias="assessmentStatus"
    )
    assessment_failure: str | None = Field(default=None, alias="assessmentFailure")
    reason_codes: list[AssessmentReasonCode] = Field(default_factory=list, alias="reasonCodes")
    missing_evidence: list[str] = Field(default_factory=list, alias="missingEvidence")
    content_overlap: ContentOverlapResult | None = Field(default=None, alias="contentOverlap")


class ResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vulnerable: int = Field(ge=0)
    protected: int = Field(ge=0)
    inconclusive: int = Field(ge=0)


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_ref: str | None = Field(default=None, alias="$schema")
    schema_version: str = Field(default="1.0", alias="schemaVersion")
    run_id: str = Field(alias="runId")
    judge_pipeline: Literal["evidence-and-content"] | None = Field(
        default=None, alias="judgePipeline"
    )
    task: TaskReference
    started_at: datetime = Field(alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    outcome: ExecutionOutcome
    configuration: ExperimentConfig
    summary: ResultSummary
    cases: list[CaseResult]
    findings: list[dict[str, object]]
    errors: list[str]
