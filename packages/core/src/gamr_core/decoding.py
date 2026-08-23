from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .states import DecodingFailureCode, DecodingStatus


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


class DecodingStream(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    state: Literal["captured", "empty", "redacted", "suppressed", "unavailable"]
    value: str | None = Field(default=None, max_length=16_384)

    @model_validator(mode="after")
    def validate_value(self) -> DecodingStream:
        if self.state == "captured" and self.value is None:
            raise ValueError("captured stream must include a value")
        if self.state != "captured" and self.value is not None:
            raise ValueError("only captured streams may include a value")
        return self


class DecodingExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    exit_code: int | None = Field(default=None, alias="exitCode")
    elapsed_seconds: float = Field(alias="elapsedSeconds", ge=0)
    timed_out: bool = Field(default=False, alias="timedOut")
    output_limited: bool = Field(default=False, alias="outputLimited")
    stdout: DecodingStream
    stderr: DecodingStream


class DecodingAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attempt: int = Field(ge=1, le=3)
    stage: str = Field(min_length=1, max_length=64)
    source: str | None = Field(default=None, max_length=65_536)
    program_sha256: str = Field(alias="programSha256", pattern=r"^[0-9a-f]{64}$")
    execution: DecodingExecutionResult | None = None
    failure_code: DecodingFailureCode | None = Field(default=None, alias="failureCode")
    failure_detail: str | None = Field(default=None, alias="failureDetail", max_length=300)
    derived_files: list[DerivedContentFile] = Field(
        default_factory=list, alias="derivedFiles", max_length=256
    )


class DecodingProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: DecodingStatus
    action: Literal["direct", "execute"] | None = None
    rationale: str | None = Field(default=None, max_length=600)
    attempt_count: int = Field(default=0, alias="attemptCount", ge=0, le=3)
    failure_code: DecodingFailureCode | None = Field(default=None, alias="failureCode")
    failure_stage: str | None = Field(default=None, alias="failureStage", max_length=64)
    program_sha256: list[str] = Field(default_factory=list, alias="programSha256", max_length=3)
    limit_flags: DecodingLimitFlags = Field(
        default_factory=DecodingLimitFlags, alias="limitFlags"
    )
    derived_files: list[DerivedContentFile] = Field(
        default_factory=list, alias="derivedFiles"
    )
    attempts: list[DecodingAttempt] = Field(default_factory=list, max_length=3)

    @field_validator("program_sha256")
    @classmethod
    def validate_program_digests(cls, digests: list[str]) -> list[str]:
        pattern = re.compile(r"^[0-9a-f]{64}$")
        for digest in digests:
            if not pattern.match(digest):
                raise ValueError(f"invalid program SHA-256 digest: {digest}")
        return digests

    @model_validator(mode="after")
    def validate_provenance_consistency(self) -> DecodingProvenance:
        if len(self.program_sha256) != self.attempt_count:
            raise ValueError("programSha256 count must equal attemptCount")
        if self.attempts:
            if len(self.attempts) != self.attempt_count:
                raise ValueError("attempts count must equal attemptCount")
            if [item.program_sha256 for item in self.attempts] != self.program_sha256:
                raise ValueError("attempt program hashes must match programSha256")
        if self.action == "direct" and self.attempt_count:
            raise ValueError("direct decoding cannot have execution attempts")
        return self
