from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from gamr_core import Scenario
from gamr_core.identifiers import new_id
from pydantic import ValidationError

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway, StructuredModelGateway
from ..ports.tracing import TracePort, trace_span
from ..scientist_prompt import (
    ADVERSARIAL_RESEARCHER_GENERATION_SYSTEM,
    AdversarialResearcherScenarioDraft,
)
from .activity import RunEvents
from .artifacts import write_raw, write_scenario
from .records import LoadedTask
from .scientist_attempts import build_attempt_record
from .scientist_input import GenerationInput
from .scientist_scenario import (
    decode_scenario_payload,
    escape_scientist_placeholders,
    prepare_scientist_scenario,
    validate_scientist_placeholders,
)

SCIENTIST_RETRY_LIMIT = 2
SCIENTIST_OUTPUT_TOKENS = 8192
SCIENTIST_GENERATION_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class GenerationResult:
    scenario: Scenario | None
    error: str | None


async def complete_scientist(
    model: ModelGateway,
    prompt: str,
    *,
    output_tokens: int,
) -> dict[str, object]:
    structured = callable(getattr(model, "complete_structured", None))
    if structured:
        structured_model = cast(StructuredModelGateway, model)
        request = structured_model.complete_structured(
            prompt,
            system=ADVERSARIAL_RESEARCHER_GENERATION_SYSTEM,
            json_schema=cast(
                dict[str, object],
                AdversarialResearcherScenarioDraft.model_json_schema(by_alias=True),
            ),
            schema_name="scientist_scenario",
            max_tokens=output_tokens,
        )
    else:
        request = model.complete(prompt)
    return await asyncio.wait_for(request, timeout=SCIENTIST_GENERATION_TIMEOUT_SECONDS)


async def generate_scenario(
    *,
    task: LoadedTask,
    model: ModelGateway,
    generation_input: GenerationInput,
    iteration: int,
    used_ids: set[str],
    run_id: str,
    artifacts: ArtifactStore | None,
    events: RunEvents,
    output_tokens: int,
    trace_port: TracePort | None,
) -> GenerationResult:
    content: str | None = None
    scenario: Scenario | None = None
    generation_prompt = generation_input.prompt
    structured = callable(getattr(model, "complete_structured", None))
    model_name = str(getattr(model, "model", type(model).__name__))
    for attempt in range(1, SCIENTIST_RETRY_LIMIT + 2):
        content = None
        completion = None
        started = perf_counter()
        prompt_bytes = len(generation_prompt.encode("utf-8"))
        events.emit(
            "scientist.generation_started",
            run_id,
            phase="scientist",
            turn=iteration,
            detail=f"attempt {attempt}",
            metadata_extra={
                "model": model_name,
                "estimatedInputTokens": (len(generation_prompt.encode("utf-8")) + 2) // 3,
                "promptBytes": prompt_bytes,
                "historyRecordCount": generation_input.history_record_count,
                "maxOutputTokens": output_tokens,
            },
        )
        try:
            with trace_span(
                trace_port,
                f"generation attempt:{attempt}",
                metadata={"attempt": attempt, "iteration": iteration, "runId": run_id},
            ):
                completion = await complete_scientist(
                    model, generation_prompt, output_tokens=output_tokens
                )
        except TimeoutError:
            duration_ms = round((perf_counter() - started) * 1000)
            error = (
                "scientist generation timed out after "
                f"{SCIENTIST_GENERATION_TIMEOUT_SECONDS} seconds"
            )
            write_raw(
                artifacts,
                run_id,
                new_id(),
                build_attempt_record(
                    generation_input=generation_input,
                    generation_prompt=generation_prompt,
                    iteration=iteration,
                    attempt=attempt,
                    model_name=model_name,
                    structured=structured,
                    output_tokens=output_tokens,
                    timeout_seconds=SCIENTIST_GENERATION_TIMEOUT_SECONDS,
                    duration_ms=duration_ms,
                    completion=None,
                    content=None,
                    error=error,
                ),
            )
            events.emit(
                "scientist.generation_failed",
                run_id,
                phase="scientist",
                turn=iteration,
                detail=error,
                metadata_extra={"durationMs": duration_ms},
            )
            events.emit("scientist.failed", run_id, phase="scientist", turn=iteration, detail=error)
            return GenerationResult(scenario, error)
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000)
            error = f"scientist generation failed: {type(exc).__name__}: {exc}"
            write_raw(
                artifacts,
                run_id,
                new_id(),
                build_attempt_record(
                    generation_input=generation_input,
                    generation_prompt=generation_prompt,
                    iteration=iteration,
                    attempt=attempt,
                    model_name=model_name,
                    structured=structured,
                    output_tokens=output_tokens,
                    timeout_seconds=SCIENTIST_GENERATION_TIMEOUT_SECONDS,
                    duration_ms=duration_ms,
                    completion=None,
                    content=None,
                    error=error,
                ),
            )
            events.emit(
                "scientist.generation_failed",
                run_id,
                phase="scientist",
                turn=iteration,
                detail=error,
                metadata_extra={"durationMs": duration_ms},
            )
            events.emit("scientist.failed", run_id, phase="scientist", turn=iteration, detail=error)
            return GenerationResult(scenario, error)

        duration_ms = round((perf_counter() - started) * 1000)
        raw_content = completion.get("content")
        if isinstance(raw_content, str):
            content = raw_content
        try:
            payload = decode_scenario_payload(completion, structured=structured)
            declared_vars = set(task.manifest.spec.variables)
            scenario = prepare_scientist_scenario(payload, iteration, used_ids)
            scenario = escape_scientist_placeholders(scenario, declared_vars)
            validate_scientist_placeholders(scenario, declared_vars)
            used_ids.add(scenario.metadata.id)
            write_scenario(artifacts, run_id, scenario)
        except (ValueError, TypeError, ValidationError) as exc:
            error = f"scientist scenario {iteration} invalid: {exc}"
            write_raw(
                artifacts,
                run_id,
                new_id(),
                build_attempt_record(
                    generation_input=generation_input,
                    generation_prompt=generation_prompt,
                    iteration=iteration,
                    attempt=attempt,
                    model_name=model_name,
                    structured=structured,
                    output_tokens=output_tokens,
                    timeout_seconds=SCIENTIST_GENERATION_TIMEOUT_SECONDS,
                    duration_ms=duration_ms,
                    completion=completion,
                    content=content,
                    error=error,
                ),
            )
            events.emit(
                "scientist.generation_completed",
                run_id,
                phase="scientist",
                turn=iteration,
                detail="invalid scenario",
                metadata_extra={
                    "durationMs": duration_ms,
                    "validationStatus": "failed",
                    "contentChars": len(content) if content else 0,
                },
            )
            retryable_empty = (
                not content
                and completion.get("finishReason") in {"stop", "length"}
                and not completion.get("refusal")
            )
            if (content or retryable_empty) and attempt < SCIENTIST_RETRY_LIMIT + 1:
                correction_error = (
                    "; ".join(str(item["msg"]) for item in exc.errors())
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )
                generation_prompt = (
                    f"{generation_input.prompt}\n\nYour previous response was not a valid "
                    f"scientist scenario: {correction_error}\n"
                    "Return one corrected JSON scenario only, "
                    "without analysis, rationale, or Markdown fences."
                )
                continue
            events.emit("scientist.failed", run_id, phase="scientist", turn=iteration, detail=error)
            return GenerationResult(scenario, error)

        write_raw(
            artifacts,
            run_id,
            new_id(),
            build_attempt_record(
                generation_input=generation_input,
                generation_prompt=generation_prompt,
                iteration=iteration,
                attempt=attempt,
                model_name=model_name,
                structured=structured,
                output_tokens=output_tokens,
                timeout_seconds=SCIENTIST_GENERATION_TIMEOUT_SECONDS,
                duration_ms=duration_ms,
                completion=completion,
                content=content,
                error=None,
            ),
        )
        events.emit(
            "scientist.generation_completed",
            run_id,
            phase="scientist",
            turn=iteration,
            detail="valid scenario",
            metadata_extra={
                "durationMs": duration_ms,
                "validationStatus": "valid",
                "contentChars": len(content) if content else 0,
            },
        )
        break
    return GenerationResult(scenario, None)
