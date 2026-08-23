from __future__ import annotations

from typing import Any

from gamr_core import (
    DecodingAttempt,
    DecodingExecutionResult,
    DecodingFailureCode,
    DecodingStream,
    DerivedContentFile,
)


def stream_record(value: str) -> DecodingStream:
    return DecodingStream(state="captured", value=value) if value else DecodingStream(state="empty")


def build_attempt(
    *,
    attempt_number: int,
    source: str,
    execution: Any,
    stage: str,
    program_digest: str,
    failure_code: DecodingFailureCode | None = None,
    derived_files: list[DerivedContentFile] | None = None,
) -> DecodingAttempt:
    execution_model = None
    if execution is not None:
        execution_model = DecodingExecutionResult(
            exitCode=execution.exit_code,
            elapsedSeconds=execution.elapsed_seconds,
            timedOut=execution.timed_out,
            outputLimited=execution.output_limited,
            stdout=stream_record(execution.stdout),
            stderr=stream_record(execution.stderr),
        )
    return DecodingAttempt(
        attempt=attempt_number,
        stage=stage,
        source=source,
        programSha256=program_digest,
        execution=execution_model,
        failureCode=failure_code,
        derivedFiles=derived_files or [],
    )
