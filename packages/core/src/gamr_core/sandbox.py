from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SandboxOperationState(StrEnum):
    REQUESTED = "requested"
    READY = "ready"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    COLLECTION_STARTED = "collection_started"
    COLLECTION_COMPLETED = "collection_completed"
    CLOSING = "closing"
    CLOSED = "closed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


SandboxPreviewTextState = Literal[
    "captured", "empty", "redacted", "suppressed", "unavailable"
]

def sanitize_sandbox_text(
    value: str, secrets: Iterable[str] = (), *, paths: bool = True
) -> str:
    return value


def sandbox_stream_is_safe(value: str) -> bool:
    return "\x00" not in value


class SandboxPreviewText(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    state: SandboxPreviewTextState
    value: str | None = Field(default=None, max_length=65_536)

    @model_validator(mode="after")
    def validate_value(self) -> SandboxPreviewText:
        if self.state == "captured" and self.value is None:
            raise ValueError("captured preview text must include a value")
        if self.state != "captured" and self.value is not None:
            raise ValueError("only captured preview text may include a value")
        return self


class SandboxExecutionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    exit_code: int | None = Field(default=None, alias="exitCode")
    elapsed_seconds: float = Field(alias="elapsedSeconds", ge=0)
    timed_out: bool = Field(default=False, alias="timedOut")
    output_limited: bool = Field(default=False, alias="outputLimited")
    stdout: SandboxPreviewText
    stderr: SandboxPreviewText

    @model_validator(mode="after")
    def validate_stream_bounds(self) -> SandboxExecutionPreview:
        for stream in (self.stdout, self.stderr):
            if stream.value is not None and len(stream.value) > 16_384:
                raise ValueError("execution preview streams are limited to 16384 characters")
        return self


class SandboxOperationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    operation_id: str = Field(alias="operationId", min_length=1, max_length=120)
    owner: str = Field(default="judge", min_length=1, max_length=100)
    state: SandboxOperationState
    generation: int = Field(ge=1, le=16)
    attempt: int | None = Field(default=None, ge=1, le=3)
    program_sha256: str | None = Field(
        default=None, alias="programSha256", pattern=r"^[0-9a-f]{64}$"
    )
    source: SandboxPreviewText | None = None
    execution: SandboxExecutionPreview | None = None
    output_count: int | None = Field(default=None, alias="outputCount", ge=0, le=256)
    failure_code: str | None = Field(default=None, alias="failureCode", max_length=100)
    failure_detail: str | None = Field(default=None, alias="failureDetail", max_length=300)

    @model_validator(mode="after")
    def validate_state_payload(self) -> SandboxOperationEvent:
        execution_states = {
            SandboxOperationState.EXECUTION_COMPLETED,
            SandboxOperationState.FAILED,
        }
        source_states = {
            SandboxOperationState.EXECUTION_STARTED,
            SandboxOperationState.EXECUTION_COMPLETED,
            SandboxOperationState.FAILED,
        }
        if self.execution is not None and self.state not in execution_states:
            raise ValueError("execution is only valid on execution completion or failure")
        if self.source is not None and self.state not in source_states:
            raise ValueError("source is only valid on execution start, completion, or failure")
        if self.output_count is not None and self.state not in {
            SandboxOperationState.COLLECTION_COMPLETED,
            SandboxOperationState.EXECUTION_COMPLETED,
        }:
            raise ValueError("output count is only valid after execution or collection")
        if self.state is SandboxOperationState.EXECUTION_STARTED and self.attempt is None:
            raise ValueError("execution start requires an attempt")
        return self


class SandboxOperationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attempt: int = Field(ge=1, le=3)
    generation: int = Field(ge=1, le=16)
    state: Literal["running", "completed", "failed", "cancelled"]
    program_sha256: str | None = Field(
        default=None, alias="programSha256", pattern=r"^[0-9a-f]{64}$"
    )
    source: SandboxPreviewText | None = None
    execution: SandboxExecutionPreview | None = None
    output_count: int | None = Field(default=None, alias="outputCount", ge=0, le=256)
    failure_code: str | None = Field(default=None, alias="failureCode", max_length=100)


class SandboxOperationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    operation_id: str = Field(alias="operationId", min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=100)
    state: SandboxOperationState
    generation: int = Field(ge=1, le=16)
    attempts: list[SandboxOperationAttempt] = Field(default_factory=list, max_length=3)
    started_at: datetime | None = Field(default=None, alias="startedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
