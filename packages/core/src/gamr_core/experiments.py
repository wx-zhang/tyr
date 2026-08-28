from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from .decoding import DecodingProvenance
from .states import (
    AssessmentReasonCode,
    AssessmentStatus,
    CompletionOutcome,
    ContentMatchType,
    ContentOverlapStatus,
    ExperimentState,
    ObjectiveStatus,
    SecurityVerdict,
)


class ExperimentSource(StrEnum):
    CLI = "cli"
    SERVICE = "service"


class TaskReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    digest: str


class ExperimentPresetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    action_mode: str = Field(
        default="read_only", alias="actionMode", pattern=r"^(read_only|approval_required)$"
    )
    model: str = ""
    adversarial_researcher_model: str = Field(
        default="", alias="adversarialResearcherModel",
        validation_alias=AliasChoices("adversarialResearcherModel", "scientistModel"),
    )
    judge_model: str = Field(default="", alias="judgeModel")
    max_turns: int = Field(default=40, alias="maxTurns", ge=1)
    discovery_turns: int = Field(default=20, alias="discoveryTurns", ge=1)
    scenario_ids: list[str] | None = Field(
        default=None,
        alias="scenarioIds",
        validation_alias=AliasChoices("scenarioIds", "caseIds"),
    )
    research_iterations: int = Field(
        default=0,
        alias="researchIterations",
        validation_alias=AliasChoices("researchIterations", "scientistIterations"),
        ge=0,
    )
    history_test_runs: int = Field(default=10, alias="historyTestRuns", ge=0, le=100)
    history_research_runs: int = Field(
        default=5,
        alias="historyResearchRuns",
        validation_alias=AliasChoices("historyResearchRuns", "historyScientistRuns"),
        ge=0,
        le=100,
    )
    max_concurrent_scenario_executions: int = Field(
        default=5,
        alias="maxConcurrentScenarioExecutions",
        validation_alias=AliasChoices("maxConcurrentScenarioExecutions", "maxConcurrentCases"),
        ge=1,
        le=5,
    )

    @model_validator(mode="after")
    def require_execution_work(self) -> ExperimentPresetConfig:
        if self.scenario_ids == [] and self.research_iterations == 0:
            raise ValueError(
                "select at least one scenario or enable research iterations "
                "(legacy: scientist iterations) for execution"
            )
        return self

    @property
    def scientist_model(self) -> str:
        return self.adversarial_researcher_model

    @property
    def case_ids(self) -> list[str] | None:
        return self.scenario_ids

    @property
    def scientist_iterations(self) -> int:
        return self.research_iterations

    @property
    def history_scientist_runs(self) -> int:
        return self.history_research_runs

    @property
    def max_concurrent_cases(self) -> int:
        return self.max_concurrent_scenario_executions


class ExperimentPresetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    configuration: ExperimentPresetConfig = Field(default_factory=ExperimentPresetConfig)
    created_at: datetime = Field(alias="createdAt")


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    source: ExperimentSource = ExperimentSource.CLI
    experiment_preset_id: str | None = Field(
        default=None,
        alias="experimentPresetId",
        validation_alias=AliasChoices("experimentPresetId", "experimentId"),
    )
    retry_of: str | None = Field(default=None, alias="retryOf")
    name: str | None = Field(default=None)
    task: str = Field(min_length=1)
    state: ExperimentState = ExperimentState.QUEUED
    configuration: ExperimentPresetConfig = Field(default_factory=ExperimentPresetConfig)
    result_path: str | None = Field(default=None, alias="resultPath")
    error_summary: str | None = Field(default=None, alias="errorSummary")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")
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

    @property
    def experiment_id(self) -> str | None:
        return self.experiment_preset_id


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


class ContentOverlapResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: ContentOverlapStatus
    assessment_status: AssessmentStatus = Field(alias="assessmentStatus")
    failure: str | None = None
    summary: str | None = Field(default=None, max_length=4000)
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


class ScenarioExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    scenario_id: str = Field(alias="scenarioId", min_length=1)
    scenario_execution_id: str = Field(
        alias="scenarioExecutionId",
        validation_alias=AliasChoices("scenarioExecutionId", "caseId"),
        min_length=1,
    )
    outcome: CompletionOutcome
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

    @model_validator(mode="before")
    @classmethod
    def normalize_historical_identity(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        legacy_id = payload.pop("caseId", None)
        definition_id = payload.get("scenarioId")
        execution_id = payload.get("scenarioExecutionId", legacy_id)
        if definition_id is None:
            definition_id = legacy_id or execution_id
        if execution_id is None:
            execution_id = definition_id
        if definition_id is not None:
            payload["scenarioId"] = definition_id
        if execution_id is not None:
            payload["scenarioExecutionId"] = execution_id
        return payload


class ResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vulnerable: int = Field(ge=0)
    protected: int = Field(ge=0)
    inconclusive: int = Field(ge=0)


class ExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    schema_ref: str | None = Field(default=None, alias="$schema")
    schema_version: str = Field(default="1.0", alias="schemaVersion")
    experiment_id: str = Field(alias="runId", min_length=1)
    judge_pipeline: Literal["evidence-and-content"] | None = Field(
        default=None, alias="judgePipeline"
    )
    task: TaskReference
    started_at: datetime = Field(alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    outcome: CompletionOutcome
    configuration: ExperimentPresetConfig
    summary: ResultSummary
    scenario_executions: list[ScenarioExecutionResult] = Field(
        default_factory=list,
        alias="scenarioExecutions",
        validation_alias=AliasChoices("scenarioExecutions", "cases"),
    )
    findings: list[dict[str, object]]
    errors: list[str]

    @model_validator(mode="before")
    @classmethod
    def normalize_historical_scenarios(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        legacy_cases = payload.pop("cases", None)
        if "scenarioExecutions" not in payload and legacy_cases is not None:
            payload["scenarioExecutions"] = legacy_cases
        return payload

    @property
    def run_id(self) -> str:
        return self.experiment_id

    @property
    def cases(self) -> list[ScenarioExecutionResult]:
        return self.scenario_executions


class ExperimentConfig(ExperimentPresetConfig):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = super().model_dump(*args, **kwargs)
        if kwargs.get("by_alias"):
            replacements = {
                "adversarialResearcherModel": "scientistModel",
                "scenarioIds": "caseIds",
                "researchIterations": "scientistIterations",
                "historyResearchRuns": "historyScientistRuns",
                "maxConcurrentScenarioExecutions": "maxConcurrentCases",
            }
            for source, target in replacements.items():
                if source in payload:
                    payload[target] = payload.pop(source)
        return payload


class RunRecord(ExperimentRecord):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = super().model_dump(*args, **kwargs)
        if kwargs.get("by_alias") and "experimentPresetId" in payload:
            payload["experimentId"] = payload.pop("experimentPresetId")
        return payload


RunSource = ExperimentSource
CaseResult = ScenarioExecutionResult
RunResult = ExperimentResult
