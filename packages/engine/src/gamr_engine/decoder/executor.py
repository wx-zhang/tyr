from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from gamr_core import DecodingAttempt, DecodingFailureCode

from ..ports.sandbox import (
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxInfrastructureError,
    SandboxUnavailableError,
    SandboxValidationError,
)
from .feedback import create_tool_feedback
from .output import prepare_decoded_output
from .records import build_attempt

if TYPE_CHECKING:
    from .loop import DecoderLoopResult


def _failure(loop: Any, *args: Any, **kwargs: Any) -> DecoderLoopResult:
    return cast("DecoderLoopResult", loop._fail_closed(*args, **kwargs))


async def execute_tool_attempt(
    loop: Any,
    call_id: str,
    source: str,
    rationale: str,
    attempt_number: int,
) -> DecoderLoopResult | None:
    del rationale
    source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    loop.program_digests.append(source_digest)
    if loop.active_sandbox_id is None:
        try:
            loop.active_sandbox_id = await start_sandbox(loop)
        except SandboxUnavailableError:
            return _failure(
                loop,
                DecodingFailureCode.SANDBOX_UNAVAILABLE,
                stage="startup",
                source=source,
                attempt_number=attempt_number,
            )
        except SandboxValidationError:
            return _failure(
                loop,
                DecodingFailureCode.INPUT_VALIDATION,
                stage="input_validation",
                source=source,
                attempt_number=attempt_number,
            )
        except Exception:
            return _failure(
                loop,
                DecodingFailureCode.INFRASTRUCTURE_FAILURE,
                stage="startup",
                source=source,
                attempt_number=attempt_number,
            )

    sandbox_id = cast(SandboxId, loop.active_sandbox_id)
    loop._activity(
        "decoder.attempt_started",
        f"Decoder attempt {attempt_number} started",
        {"attempt": attempt_number, "programSha256": source_digest},
    )
    attempt_dir = f"output/attempt-{attempt_number:03d}"
    try:
        execution = await loop.sandbox.execute(sandbox_id, source)
    except SandboxUnavailableError:
        return _failure(
            loop,
            DecodingFailureCode.SANDBOX_UNAVAILABLE,
            stage="execution",
            source=source,
            attempt_number=attempt_number,
        )
    except SandboxClosedError, SandboxInfrastructureError:
        return _failure(
            loop,
            DecodingFailureCode.INFRASTRUCTURE_FAILURE,
            stage="execution",
            source=source,
            attempt_number=attempt_number,
        )
    except Exception:
        return _failure(
            loop,
            DecodingFailureCode.INFRASTRUCTURE_FAILURE,
            stage="execution",
            source=source,
            attempt_number=attempt_number,
        )

    loop.limit_flags.timed_out |= execution.timed_out
    loop.limit_flags.output_limited |= execution.output_limited
    terminal_destruction = execution.timed_out or execution.output_limited
    collected: Sequence[SandboxEntry] = ()
    if not terminal_destruction:
        try:
            collected = await loop.sandbox.collect_output(sandbox_id, attempt_dir)
        except SandboxValidationError:
            return _failure(
                loop,
                DecodingFailureCode.INVALID_OUTPUT_TREE,
                stage="output_validation",
                source=source,
                attempt_number=attempt_number,
                execution=execution,
            )
        except Exception:
            return _failure(
                loop,
                DecodingFailureCode.INFRASTRUCTURE_FAILURE,
                stage="collection",
                source=source,
                attempt_number=attempt_number,
                execution=execution,
            )
    if terminal_destruction:
        await destroy_active_sandbox(loop)

    loop._activity(
        "decoder.attempt_completed",
        f"Decoder attempt {attempt_number} completed",
        {
            "attempt": attempt_number,
            "exitCode": execution.exit_code if execution.exit_code is not None else -1,
            "outputCount": len(collected),
            "stage": "output_validation" if collected else "execution",
        },
    )
    if collected and execution.exit_code == 0:
        decoded = prepare_decoded_output(
            entries=collected,
            snapshots=loop.snapshots,
            source=source,
            execution=execution,
            attempt_number=attempt_number,
            program_digest=source_digest,
            previous_attempts=loop.attempts,
            limit_flags=loop.limit_flags,
            rationale=loop.route_rationale,
            attempt_builder=loop._attempt_record,
        )
        if decoded is not None:
            provenance, snapshots = decoded
            return cast("DecoderLoopResult", loop._decoded_result(provenance, snapshots))

    record_attempt(
        loop, attempt_number=attempt_number, source=source, execution=execution, stage="execution"
    )
    if attempt_number == loop.max_attempts:
        return None
    loop.messages.append(
        create_tool_feedback(
            call_id=call_id,
            attempt=attempt_number,
            result=execution,
            entries=collected,
        )
    )
    return None


async def start_sandbox(loop: Any) -> SandboxId:
    entries = [
        SandboxEntry(path=f"{snapshot.snapshot_id}/{snapshot.filename}", content=snapshot.content)
        for snapshot in loop.snapshots
    ]
    return cast(SandboxId, await loop.sandbox.start(entries))


async def destroy_active_sandbox(loop: Any) -> None:
    if loop.active_sandbox_id is None:
        return
    sandbox_id = loop.active_sandbox_id
    loop.active_sandbox_id = None
    try:
        await loop.sandbox.close(sandbox_id)
    except Exception:
        pass


async def cleanup(loop: Any) -> None:
    await destroy_active_sandbox(loop)


def record_attempt(
    loop: Any,
    *,
    attempt_number: int,
    source: str,
    execution: Any,
    stage: str,
    failure_code: DecodingFailureCode | None = None,
    derived_files: list[Any] | None = None,
) -> None:
    loop.attempts.append(
        attempt_record(
            loop,
            attempt_number=attempt_number,
            source=source,
            execution=execution,
            stage=stage,
            failure_code=failure_code,
            derived_files=derived_files,
        )
    )


def attempt_record(
    loop: Any,
    *,
    attempt_number: int,
    source: str,
    execution: Any,
    stage: str,
    failure_code: DecodingFailureCode | None = None,
    derived_files: list[Any] | None = None,
) -> DecodingAttempt:
    return build_attempt(
        attempt_number=attempt_number,
        source=source,
        execution=execution,
        stage=stage,
        program_digest=loop.program_digests[attempt_number - 1],
        failure_code=failure_code,
        derived_files=derived_files,
    )
