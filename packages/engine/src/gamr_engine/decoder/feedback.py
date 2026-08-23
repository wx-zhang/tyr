from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from ..ports.sandbox import ExecutionResult, SandboxEntry


def create_tool_feedback(
    *,
    call_id: str,
    attempt: int,
    result: ExecutionResult,
    entries: Sequence[SandboxEntry],
    max_attempts: int,
    error_detail: str | None = None,
) -> dict[str, Any]:
    """
    Constructs coarse feedback tool message for the model.
    Never includes stdout, stderr, exception messages, decoded bytes, source, or host/sandbox paths.
    """
    outputs_summary = []
    for entry in entries:
        outputs_summary.append(
            {
                "path": entry.path,
                "size": len(entry.content),
                "sha256": hashlib.sha256(entry.content).hexdigest(),
            }
        )

    feedback_payload: dict[str, Any] = {
        "attempt": attempt,
        "exitCode": result.exit_code,
        "timedOut": result.timed_out,
        "outputLimited": result.output_limited,
        "stdoutAvailableToModel": False,
        "stderrAvailableToModel": False,
        "outputCount": len(entries),
        "outputs": outputs_summary,
        "attemptsRemaining": max_attempts - attempt,
    }
    if attempt < max_attempts:
        next_root = f"/workspace/output/attempt-{attempt + 1:03d}"
        feedback_payload["nextAttemptOutputRoot"] = next_root
        feedback_payload["guidance"] = (
            "If the original uploads are directly readable, return action direct. "
            "Otherwise the next execution must write at least one derived file under "
            f"{next_root}/<snapshot_id>/."
        )
    else:
        feedback_payload["guidance"] = (
            "No execution attempts remain. Return action direct only if the original uploads "
            "are directly readable. Do not request another tool call."
        )

    if error_detail:
        feedback_payload["error"] = error_detail

    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(feedback_payload, ensure_ascii=False),
    }
