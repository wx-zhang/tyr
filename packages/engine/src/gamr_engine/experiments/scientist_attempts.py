from __future__ import annotations

from .scientist_input import GenerationInput, estimated_tokens


def build_attempt_record(
    *,
    generation_input: GenerationInput,
    generation_prompt: str,
    iteration: int,
    attempt: int,
    model_name: str,
    structured: bool,
    output_tokens: int,
    timeout_seconds: int,
    duration_ms: int,
    completion: dict[str, object] | None,
    content: str | None,
    error: str | None,
) -> dict[str, object]:
    prompt_bytes = len(generation_prompt.encode("utf-8"))
    response = {
        "durationMs": duration_ms,
        "finishReason": completion.get("finishReason") if completion is not None else None,
        "contentChars": len(content) if content else 0,
        "usage": completion.get("usage") if completion is not None else None,
    }
    record: dict[str, object] = {
        "phase": "scientist",
        "iteration": iteration,
        "attempt": attempt,
        "model": model_name,
        "input": {
            "promptChars": len(generation_prompt),
            "promptBytes": prompt_bytes,
            "estimatedTokens": estimated_tokens(generation_prompt),
            "historyChars": len(generation_input.history),
            "historyRecordCount": generation_input.history_record_count,
            "historyCaseIds": list(generation_input.history_case_ids),
            "historyTruncated": generation_input.history_truncated,
        },
        "request": {
            "structured": structured,
            "schemaName": "scientist_scenario",
            "maxOutputTokens": output_tokens,
            "timeoutSeconds": timeout_seconds,
        },
        "response": response,
        "prompt": generation_prompt,
        "completion": completion,
        "validation": {
            "status": "failed" if error is not None else "valid",
            "errors": [error] if error is not None else [],
        },
    }
    if completion is not None:
        record["content"] = content
    return record
