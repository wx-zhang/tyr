import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
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


def _load_bytes(case_root: Path, relative: str, kind: str) -> bytes:
    path = (case_root / relative).resolve()
    if case_root != path and case_root not in path.parents:
        raise ValueError(f"{kind} path escapes case directory")
    if not path.is_file():
        raise ValueError(f"{kind} file is missing: {relative}")
    return path.read_bytes()


def _verified_file(case_root: Path, document: Any, kind: str) -> LoadedFile:
    content = _load_bytes(case_root, document.path, kind)
    if len(content) != document.size:
        raise ValueError(f"{kind} size mismatch: {document.path}")
    if hashlib.sha256(content).hexdigest() != document.sha256:
        raise ValueError(f"{kind} digest mismatch: {document.path}")
    return LoadedFile(document.path, document.filename, document.size, document.sha256, content)


def _load_case(root: Path, document: CaseDocument) -> LoadedCase:
    case_root = (root / "cases" / document.id).resolve()
    if root != case_root and root not in case_root.parents:
        raise ValueError("case path escapes dataset directory")
    reference = _verified_file(case_root, document.reference, "reference")
    try:
        reference_text = reference.content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("reference must be UTF-8 text") from error
    if not reference_text.strip() or "\x00" in reference_text:
        raise ValueError("reference must be non-empty UTF-8 text without NUL bytes")
    attachments = [
        LoadedAttachment(
            path=att.path,
            filename=att.filename,
            size=att.size,
            sha256=att.sha256,
            content=att.content,
            file_id=item.file_id,
            content_type=item.content_type,
        )
        for item in document.attachments
        for att in [_verified_file(case_root, item, "attachment")]
    ]
    return LoadedCase(
        id=document.id,
        label=document.label,
        source_run_id=document.source.run_id,
        rationale=document.source.rationale,
        scenario=document.scenario,
        evaluation_plan=EvaluationPlan(prompt=document.evaluation_prompt),
        transcript=document.transcript,
        reference=reference,
        attachments=attachments,
        expectations=[item.model_dump(mode="json") for item in document.expectations],
    )


def load_evaluation_dataset(path: Path) -> LoadedDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = DatasetDocument.model_validate(payload)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid evaluation dataset: {error}") from error
    root = path.resolve().parent
    return LoadedDataset(
        judge_pipeline=document.judge_pipeline,
        source_path=str(path),
        cases=[_load_case(root, item) for item in document.cases],
    )
