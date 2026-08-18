from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .states import (
    AssessmentReasonCode,
    AssessmentStatus,
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
    task: TaskReference
    started_at: datetime = Field(alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    outcome: ExecutionOutcome
    configuration: ExperimentConfig
    summary: ResultSummary
    cases: list[CaseResult]
    findings: list[dict[str, object]]
    errors: list[str]
