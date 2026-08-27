from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class TaskMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class TaskVariable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["run", "literal", "discovery"]
    default: str | None = None
    value: str | None = None
    field: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> TaskVariable:
        if self.source == "literal" and self.value is None:
            raise ValueError("literal variables require a value")
        if self.source == "discovery" and not self.field:
            raise ValueError("discovery variables require a field")
        if self.source != "literal" and self.value is not None:
            raise ValueError("only literal variables may define value")
        if self.source != "discovery" and self.field is not None:
            raise ValueError("only discovery variables may define field")
        return self


class TaskDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(alias="maxTurns", ge=1)
    action_mode: str = Field(alias="actionMode", pattern=r"^(read_only|approval_required)$")
    default_case_ids: list[str] = Field(default_factory=list, alias="defaultCaseIds")

    @field_validator("default_case_ids")
    @classmethod
    def unique_case_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("default case IDs must be unique")
        return value


JudgePipelineId = Literal["evidence-and-content"]


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: JudgePipelineId = "evidence-and-content"


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    discovery: str | None = None
    methodology: str | None = None
    evaluation: str | None = None
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    cases: list[str] = Field(min_length=1)
    defaults: TaskDefaults
    variables: dict[str, TaskVariable] = Field(default_factory=dict)


class TaskManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_ref: str | None = Field(default=None, alias="$schema")
    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["task"] = "task"
    metadata: TaskMetadata
    spec: TaskSpec

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("only task schema version 1.0 is supported")
        return value


class DiscoveryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["discovery"] = "discovery"
    prompt: str = Field(min_length=1)
    output_fields: list[str] = Field(
        default_factory=lambda: ["path", "workspace", "agent"],
        alias="outputFields",
        min_length=1,
    )


class PromptBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["methodology"] = "methodology"
    system_brief: str = Field(alias="systemBrief", min_length=1)
    unsticking_guidance: str = Field(alias="unstickingGuidance", min_length=1)
    testing_methodology: str = Field(alias="testingMethodology", min_length=1)


class EvaluationReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    classification: Literal["synthetic"]


class EvaluationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["evaluation"] = "evaluation"
    prompt: str = Field(min_length=1)
    reference: EvaluationReference | None = None


class ScenarioMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str | None = Field(default=None, min_length=1)
    tags: list[str] = Field(default_factory=list)


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    success_criteria: str | None = Field(default=None, alias="successCriteria", min_length=1)
    expected_control: str = Field(alias="expectedControl", min_length=1)
    evidence_requirements: list[str] = Field(alias="evidenceRequirements", min_length=1)
    collector_evidence: Literal["request", "file"] | None = Field(
        default=None, alias="collectorEvidence"
    )


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["scenario"] = "scenario"
    metadata: ScenarioMetadata
    spec: ScenarioSpec


TaskDocument = Annotated[
    TaskManifest | DiscoveryPlan | PromptBundle | EvaluationPlan | Scenario,
    Field(discriminator="kind"),
]
_DOCUMENT_ADAPTER: TypeAdapter[TaskDocument] = TypeAdapter(TaskDocument)
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def validate_template_placeholders(text: str, declared: set[str]) -> None:
    unknown = sorted(set(_PLACEHOLDER_RE.findall(text)) - declared)
    if unknown:
        raise ValueError(f"unknown task template variables: {', '.join(unknown)}")


def escape_unknown_template_placeholders(text: str, declared: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in declared:
            return match.group(0)
        return "{{" + name + "}}"

    return _PLACEHOLDER_RE.sub(replace, text)


def render_template(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise KeyError(name)
        return values[name]

    return _PLACEHOLDER_RE.sub(replace, text).replace("{{", "{").replace("}}", "}")


def validate_document(payload: dict[str, Any]) -> TaskDocument:
    return _DOCUMENT_ADAPTER.validate_python(payload)


def load_manifest(payload: dict[str, Any]) -> TaskManifest:
    return TaskManifest.model_validate(payload)


def load_scenario(payload: dict[str, Any]) -> Scenario:
    return Scenario.model_validate(payload)


def parse_json_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object in {path}")
    return payload
