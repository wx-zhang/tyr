from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from gamr_core import (
    DecodingFailureCode,
    DecodingLimitFlags,
    DecodingProvenance,
    DecodingStatus,
    DerivedContentFile,
)

from ..collector_verification import CollectorFile
from ..content_prepare import DerivedContentSnapshot, prepare_derived_content_evidence
from ..content_source import VerifiedContentSnapshot
from ..ports.models import ChatModelGateway
from ..ports.sandbox import (
    Sandbox,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxInfrastructureError,
    SandboxUnavailableError,
)
from .feedback import create_tool_feedback
from .prompts import build_decoder_initial_messages
from .tools import EXECUTE_PYTHON_TOOL, parse_tool_call


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
    ) -> None:
        self.model = model
        self.sandbox = sandbox
        self.snapshots = list(snapshots)
        self.task_context = task_context
        self.case_fields = case_fields
        self.evaluation_criteria = evaluation_criteria
        self.transcript = transcript
        self.max_attempts = max_attempts

        self.messages: list[dict[str, Any]] = []
        self.active_sandbox_id: SandboxId | None = None
        self.program_digests: list[str] = []
        self.limit_flags = DecodingLimitFlags()

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

        try:
            for attempt_idx in range(1, self.max_attempts + 1):
                res = await self._step(attempt_idx)
                if res is not None:
                    return res
            return self._fail_closed(
                DecodingFailureCode.ATTEMPT_EXHAUSTION,
                attempt_count=self.max_attempts,
            )
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

        call_id, source, parse_err = parse_tool_call(tool_calls[0])
        if parse_err is not None:
            code = (
                DecodingFailureCode.UNKNOWN_TOOL_OR_INPUT
                if parse_err == "unknown_tool_or_input"
                else DecodingFailureCode.INVALID_AGENT_RESPONSE
            )
            return self._fail_closed(code)

        assert call_id is not None and source is not None
        self.messages.append(msg)
        return await self._execute_tool_attempt(call_id, source, attempt_number)

    def _handle_text_response(self, content: Any) -> DecoderLoopResult:
        if not isinstance(content, str) or not content.strip():
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = "\n".join(stripped.splitlines()[1:-1]).strip()

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

        if isinstance(payload, dict) and payload.get("action") == "direct":
            prov = DecodingProvenance(
                status=DecodingStatus.SKIPPED,
                attemptCount=len(self.program_digests),
                programSha256=self.program_digests,
                limitFlags=self.limit_flags,
                derivedFiles=[],
            )
            return DecoderLoopResult("direct", prov, [])

        return self._fail_closed(DecodingFailureCode.INVALID_AGENT_RESPONSE)

    async def _execute_tool_attempt(
        self, call_id: str, source: str, attempt_number: int
    ) -> DecoderLoopResult | None:
        source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.program_digests.append(source_digest)

        if self.active_sandbox_id is None:
            try:
                self.active_sandbox_id = await self._start_sandbox()
            except SandboxUnavailableError:
                return self._fail_closed(DecodingFailureCode.SANDBOX_UNAVAILABLE)
            except Exception:
                return self._fail_closed(DecodingFailureCode.INFRASTRUCTURE_FAILURE)

        attempt_dir = f"/workspace/output/attempt-{attempt_number:03d}"
        try:
            exec_res = await self.sandbox.execute(self.active_sandbox_id, source)
        except (SandboxUnavailableError, SandboxClosedError, SandboxInfrastructureError):
            return self._fail_closed(DecodingFailureCode.INFRASTRUCTURE_FAILURE)
        except Exception:
            return self._fail_closed(DecodingFailureCode.INFRASTRUCTURE_FAILURE)

        if exec_res.timed_out:
            self.limit_flags.timed_out = True
        if exec_res.output_limited:
            self.limit_flags.output_limited = True

        terminal_destruction = exec_res.timed_out or exec_res.output_limited
        collected: Sequence[SandboxEntry] = ()
        if not terminal_destruction:
            try:
                collected = await self.sandbox.collect_output(self.active_sandbox_id, attempt_dir)
            except Exception:
                collected = ()

        if terminal_destruction:
            await self._destroy_active_sandbox()

        if collected and exec_res.exit_code == 0:
            derived_res = self._validate_and_prepare_output(collected)
            if derived_res is not None:
                return derived_res

        if attempt_number == self.max_attempts:
            return None

        feedback_msg = create_tool_feedback(
            call_id=call_id,
            attempt=attempt_number,
            result=exec_res,
            entries=collected,
        )
        self.messages.append(feedback_msg)
        return None

    def _validate_and_prepare_output(
        self, entries: Sequence[SandboxEntry]
    ) -> DecoderLoopResult | None:
        source_map = {
            s.snapshot_id: CollectorFile(
                file_id=s.source_file_id,
                filename=s.filename,
                content_type=s.content_type,
                size=s.size,
                sha256=s.sha256,
            )
            for s in self.snapshots
        }

        derived_snapshots = [
            DerivedContentSnapshot(relative_path=e.path, content=e.content)
            for e in entries
        ]

        collector_files = list(source_map.values())
        batch = prepare_derived_content_evidence(
            collector_files, source_map, derived_snapshots
        )

        if batch.incomplete or not batch.items:
            return None

        derived_files: list[DerivedContentFile] = []
        for item in batch.items:
            source_file = next((f for f in collector_files if f.file_id == item.file_id), None)
            if source_file is None:
                continue
            item_bytes = item.text.encode("utf-8") if item.text is not None else (item.image or b"")
            derived_files.append(
                DerivedContentFile(
                    sourceFileId=item.file_id,
                    uploadedItemId=item.uploaded_item_id,
                    sha256=hashlib.sha256(item_bytes).hexdigest(),
                    size=len(item_bytes),
                    detectedContentType=item.content_type,
                )
            )

        prov = DecodingProvenance(
            status=DecodingStatus.SUCCEEDED,
            attemptCount=len(self.program_digests),
            programSha256=self.program_digests,
            limitFlags=self.limit_flags,
            derivedFiles=derived_files,
        )
        return DecoderLoopResult("decoded", prov, derived_snapshots)

    async def _start_sandbox(self) -> SandboxId:
        entries = [
            SandboxEntry(
                path=f"/workspace/input/{s.snapshot_id}/{s.filename}",
                content=s.content,
            )
            for s in self.snapshots
        ]
        return await self.sandbox.start(entries)

    async def _destroy_active_sandbox(self) -> None:
        if self.active_sandbox_id is not None:
            sid = self.active_sandbox_id
            self.active_sandbox_id = None
            try:
                await self.sandbox.close(sid)
            except Exception:
                pass

    async def _cleanup(self) -> None:
        await self._destroy_active_sandbox()

    def _fail_closed(
        self,
        failure_code: DecodingFailureCode,
        *,
        attempt_count: int | None = None,
    ) -> DecoderLoopResult:
        count = len(self.program_digests) if attempt_count is None else attempt_count
        prov = DecodingProvenance(
            status=DecodingStatus.FAILED,
            attemptCount=count,
            failureCode=failure_code,
            programSha256=self.program_digests,
            limitFlags=self.limit_flags,
            derivedFiles=[],
        )
        return DecoderLoopResult("failed", prov, [])
