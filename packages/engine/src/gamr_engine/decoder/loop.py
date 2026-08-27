from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from gamr_core import (
    DecodingAttempt,
    DecodingFailureCode,
    DecodingLimitFlags,
    DecodingProvenance,
    DecodingStatus,
)

from ..content_prepare import DerivedContentSnapshot
from ..content_source import VerifiedContentSnapshot
from ..ports.models import ChatModelGateway
from ..ports.sandbox import Sandbox, SandboxId
from ..ports.tracing import trace_span
from .direct import originals_are_directly_readable
from .executor import (
    attempt_record,
    cleanup,
    destroy_active_sandbox,
    execute_tool_attempt,
    finalize_after_attempts,
    record_attempt,
    start_sandbox,
)
from .prompts import build_decoder_initial_messages
from .tools import EXECUTE_PYTHON_TOOL, MAX_RATIONALE_LENGTH, parse_tool_call


@dataclass(frozen=True)
class DecoderLoopResult:
    action: Literal["direct", "decoded", "failed"]
    provenance: DecodingProvenance
    derived_snapshots: list[DerivedContentSnapshot]


class DecoderExecutionLoop:
    def __init__(
        self,
        *,
        model: ChatModelGateway,
        sandbox: Sandbox,
        snapshots: Sequence[VerifiedContentSnapshot],
        task_context: str,
        case_fields: dict[str, object],
        evaluation_criteria: str,
        transcript: list[dict[str, object]],
        max_attempts: int = 3,
        activity_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.model = model
        self.sandbox = sandbox
        self.snapshots = list(snapshots)
        self.task_context = task_context
        self.case_fields = case_fields
        self.evaluation_criteria = evaluation_criteria
        self.transcript = transcript
        self.max_attempts = max_attempts
        self.activity_sink = activity_sink

        self.messages: list[dict[str, Any]] = []
        self.active_sandbox_id: SandboxId | None = None
        self.program_digests: list[str] = []
        self.limit_flags = DecodingLimitFlags()
        self.route_rationale: str | None = None
        self.attempts: list[DecodingAttempt] = []

    async def run(self) -> DecoderLoopResult:
        if self.sandbox.isolation == "unsafe":
            return self._fail_closed(DecodingFailureCode.UNSAFE_ISOLATION)
        if self.sandbox.isolation != "contained":
            return self._fail_closed(DecodingFailureCode.SANDBOX_UNAVAILABLE)

        self.messages = build_decoder_initial_messages(
            task_context=self.task_context,
            case_fields=self.case_fields,
            evaluation_criteria=self.evaluation_criteria,
            transcript=self.transcript,
            snapshots=self.snapshots,
        )
        self._activity("decoder.analysis_started", "Decoder analysis started")

        try:
            for attempt_idx in range(1, self.max_attempts + 1):
                with trace_span(
                    getattr(self.model, "trace_port", None),
                    f"decoder attempt:{attempt_idx}",
                    metadata={"attempt": attempt_idx},
                ):
                    res = await self._step(attempt_idx)
                if res is not None:
                    return res
            return await finalize_after_attempts(self)
        finally:
            await self._cleanup()

    async def _step(self, attempt_number: int) -> DecoderLoopResult | None:
        try:
            response = await self.model.chat(
                self.messages, tools=[EXECUTE_PYTHON_TOOL], max_tokens=2048
            )
        except Exception:
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        msg = response.get("message")
        if not isinstance(msg, dict):
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        tool_calls = msg.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        if not tool_calls:
            return self._handle_text_response(msg.get("content"))

        if len(tool_calls) != 1:
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        call_id, source, rationale, parse_err = parse_tool_call(tool_calls[0])
        if parse_err is not None:
            code = (
                DecodingFailureCode.UNKNOWN_TOOL_OR_INPUT
                if parse_err == "unknown_tool_or_input"
                else DecodingFailureCode.INVALID_AGENT_RESPONSE
            )
            return self._fail_closed(code)

        assert call_id is not None and source is not None and rationale is not None
        if self.route_rationale is None:
            self.route_rationale = rationale
        if attempt_number == 1:
            self._activity(
                "decoder.route_selected",
                f"Decoder selected execution: {rationale.strip()}",
                {"decoderAction": "execute"},
            )
        self.messages.append(msg)
        return await self._execute_tool_attempt(call_id, source, rationale, attempt_number)

    async def _execute_tool_attempt(
        self, call_id: str, source: str, rationale: str, attempt_number: int
    ) -> DecoderLoopResult | None:
        return await execute_tool_attempt(self, call_id, source, rationale, attempt_number)

    async def _start_sandbox(self) -> SandboxId:
        return await start_sandbox(self)

    async def _destroy_active_sandbox(self) -> None:
        await destroy_active_sandbox(self)

    async def _cleanup(self) -> None:
        await cleanup(self)

    def _handle_text_response(self, content: Any) -> DecoderLoopResult:
        if not isinstance(content, str) or not content.strip():
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = "\n".join(stripped.splitlines()[1:-1]).strip()

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = {}
        if not (isinstance(payload, dict) and payload.get("action") == "direct"):
            if originals_are_directly_readable(self.snapshots):
                payload = {
                    "action": "direct",
                    "rationale": "Verified uploads are directly readable.",
                }

        rationale = payload.get("rationale") if isinstance(payload, dict) else None
        latest_execution = self.attempts[-1].execution if self.attempts else None
        direct_allowed = not self.program_digests or (
            latest_execution is not None
            and latest_execution.exit_code == 0
            and not latest_execution.timed_out
            and not latest_execution.output_limited
        )
        if (
            isinstance(payload, dict)
            and payload.get("action") == "direct"
            and direct_allowed
            and isinstance(rationale, str)
            and rationale.strip()
            and len(rationale) <= MAX_RATIONALE_LENGTH
        ):
            prov = DecodingProvenance(
                status=DecodingStatus.SKIPPED,
                action="direct",
                rationale=rationale.strip(),
                attemptCount=len(self.program_digests),
                programSha256=self.program_digests,
                limitFlags=self.limit_flags,
                derivedFiles=[],
                attempts=self.attempts,
            )
            if self.program_digests:
                self._activity(
                    "decoder.route_revised",
                    f"Decoder revised execution to direct evaluation: {rationale.strip()}",
                    {"decoderAction": "direct"},
                )
            else:
                self._activity(
                    "decoder.route_selected",
                    f"Decoder selected direct evaluation: {rationale.strip()}",
                    {"decoderAction": "direct"},
                )
            return DecoderLoopResult("direct", prov, [])

        return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

    def _fail_closed(
        self,
        failure_code: DecodingFailureCode,
        *,
        attempt_count: int | None = None,
        stage: str = "analysis",
        source: str | None = None,
        attempt_number: int | None = None,
        execution: Any = None,
    ) -> DecoderLoopResult:
        count = len(self.program_digests) if attempt_count is None else attempt_count
        if source is not None and attempt_number is not None:
            self._record_attempt(
                attempt_number=attempt_number,
                source=source,
                execution=execution,
                stage=stage,
                failure_code=failure_code,
            )
        prov = DecodingProvenance(
            status=DecodingStatus.FAILED,
            action="execute" if self.program_digests else None,
            rationale=self.route_rationale,
            attemptCount=count,
            failureCode=failure_code,
            failureStage=stage,
            programSha256=self.program_digests,
            limitFlags=self.limit_flags,
            derivedFiles=[],
            attempts=self.attempts,
        )
        return DecoderLoopResult("failed", prov, [])

    def _decoded_result(
        self, provenance: DecodingProvenance, snapshots: list[DerivedContentSnapshot]
    ) -> DecoderLoopResult:
        return DecoderLoopResult("decoded", provenance, snapshots)

    def _record_attempt(
        self,
        *,
        attempt_number: int,
        source: str,
        execution: Any,
        stage: str,
        failure_code: DecodingFailureCode | None = None,
        derived_files: list[Any] | None = None,
    ) -> None:
        record_attempt(
            self,
            attempt_number=attempt_number,
            source=source,
            execution=execution,
            stage=stage,
            failure_code=failure_code,
            derived_files=derived_files,
        )

    def _attempt_record(
        self,
        *,
        attempt_number: int,
        source: str,
        execution: Any,
        stage: str,
        failure_code: DecodingFailureCode | None = None,
        derived_files: list[Any] | None = None,
    ) -> DecodingAttempt:
        return attempt_record(
            self,
            attempt_number=attempt_number,
            source=source,
            execution=execution,
            stage=stage,
            failure_code=failure_code,
            derived_files=derived_files,
        )

    def _activity(self, name: str, detail: str, metadata: dict[str, object] | None = None) -> None:
        if self.activity_sink is not None:
            self.activity_sink(name, {"detail": detail[:600], "metadata": metadata or {}})
