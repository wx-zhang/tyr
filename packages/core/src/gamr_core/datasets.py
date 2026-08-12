from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class DatasetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class DatasetVariable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["run", "literal", "discovery"]
    default: str | None = None
    value: str | None = None
    field: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> DatasetVariable:
        if self.source == "literal" and self.value is None:
            raise ValueError("literal variables require a value")
        if self.source == "discovery" and not self.field:
            raise ValueError("discovery variables require a field")
        if self.source != "literal" and self.value is not None:
            raise ValueError("only literal variables may define value")
        if self.source != "discovery" and self.field is not None:
            raise ValueError("only discovery variables may define field")
        return self


class DatasetDefaults(BaseModel):
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


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    discovery: str | None = None
    methodology: str | None = None
    evaluation: str | None = None
    cases: list[str] = Field(min_length=1)
    defaults: DatasetDefaults
    variables: dict[str, DatasetVariable] = Field(default_factory=dict)


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_ref: str | None = Field(default=None, alias="$schema")
    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["dataset"] = "dataset"
    metadata: DatasetMetadata
    spec: DatasetSpec

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("only dataset schema version 1.0 is supported")
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


class EvaluationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    kind: Literal["evaluation"] = "evaluation"
    prompt: str = Field(min_length=1)


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


DatasetDocument = Annotated[
    DatasetManifest | DiscoveryPlan | PromptBundle | EvaluationPlan | Scenario,
    Field(discriminator="kind"),
]
_DOCUMENT_ADAPTER: TypeAdapter[DatasetDocument] = TypeAdapter(DatasetDocument)
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def validate_template_placeholders(text: str, declared: set[str]) -> None:
    unknown = sorted(set(_PLACEHOLDER_RE.findall(text)) - declared)
    if unknown:
        raise ValueError(f"unknown dataset template variables: {', '.join(unknown)}")


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


def validate_document(payload: dict[str, Any]) -> DatasetDocument:
    return _DOCUMENT_ADAPTER.validate_python(payload)


def load_manifest(payload: dict[str, Any]) -> DatasetManifest:
    return DatasetManifest.model_validate(payload)


def load_scenario(payload: dict[str, Any]) -> Scenario:
    return Scenario.model_validate(payload)


def parse_json_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object in {path}")
    return payload
