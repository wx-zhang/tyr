from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from gamr_core import EvaluationPlan, JudgePipelineId, Scenario
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(alias="runId", min_length=1)
    rationale: str = Field(min_length=1)


class FileDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttachmentDocument(FileDocument):
    file_id: str = Field(alias="fileId", min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)


class ExpectationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(pattern=r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
    values: list[Any] = Field(min_length=1)


class CaseDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    label: Literal["positive", "negative"]
    source: SourceDocument
    scenario: Scenario
    evaluation_prompt: str = Field(alias="evaluationPrompt", min_length=1)
    transcript: list[dict[str, Any]] = Field(min_length=1)
    reference: FileDocument
    attachments: list[AttachmentDocument] = Field(min_length=1)
    expectations: list[ExpectationDocument] = Field(min_length=1)

    @field_validator("attachments")
    @classmethod
    def unique_files(cls, value: list[AttachmentDocument]) -> list[AttachmentDocument]:
        ids = [item.file_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("attachment file IDs must be unique")
        return value


class DatasetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    judge_pipeline: JudgePipelineId = Field(alias="judgePipeline")
    cases: list[CaseDocument] = Field(min_length=1)

    @field_validator("cases")
    @classmethod
    def unique_cases(cls, value: list[CaseDocument]) -> list[CaseDocument]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation case IDs must be unique")
        return value


@dataclass(frozen=True, slots=True)
class LoadedFile:
    path: str
    filename: str
    size: int
    sha256: str
    content: bytes


@dataclass(frozen=True, slots=True)
class LoadedAttachment(LoadedFile):
    file_id: str
    content_type: str


@dataclass(frozen=True, slots=True)
class LoadedCase:
    id: str
    label: str
    source_run_id: str
    rationale: str
    scenario: Scenario
    evaluation_plan: EvaluationPlan
    transcript: list[dict[str, Any]]
    reference: LoadedFile
    attachments: list[LoadedAttachment]
    expectations: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    judge_pipeline: JudgePipelineId
    source_path: str
    cases: list[LoadedCase]
