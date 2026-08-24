from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

from gamr_core import (
    SandboxExecutionPreview,
    SandboxOperationEvent,
    SandboxOperationState,
    SandboxPreviewText,
)
from gamr_core.identifiers import new_id
from gamr_core.sandbox import sandbox_stream_is_safe, sanitize_sandbox_text

from .ports.sandbox import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxSource,
    validate_source,
)

EventSink = Callable[[SandboxOperationEvent], None]


class ObservedSandbox:
    """Delegates sandbox work while recording a pipeline-neutral operation."""

    def __init__(
        self,
        inner: Sandbox,
        *,
        owner: str,
        event_sink: EventSink,
        sensitive_values: Sequence[str | bytes] = (),
        configured_secrets: Sequence[str] = (),
    ) -> None:
        self._inner = inner
        self.owner = owner
        self.operation_id = new_id()
        self._event_sink = event_sink
        self._sensitive_values = tuple(
            value.decode("utf-8", errors="ignore") if isinstance(value, bytes) else value
            for value in sensitive_values
            if value
        )
        self._configured_secrets = tuple(value for value in configured_secrets if value)
        self._generation = 0
        self._attempt = 0
        self._finished = False
        self._event_count = 0

    @property
    def isolation(self) -> Any:
        return self._inner.isolation

    @property
    def has_events(self) -> bool:
        return self._event_count > 0

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        self._emit(SandboxOperationState.REQUESTED)
        try:
            sandbox_id = await self._inner.start(entries)
        except Exception as error:
            self._fail(error)
            raise
        self._generation += 1
        self._emit(SandboxOperationState.READY)
        return sandbox_id

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        self._attempt += 1
        source_value: SandboxPreviewText | None = None
        digest: str | None = None
        try:
            source_bytes = validate_source(source)
            source_value = _source_preview(
                source_bytes.decode("utf-8"), self._configured_secrets
            )
            digest = hashlib.sha256(source_bytes).hexdigest()
        except Exception as error:
            self._fail(error, attempt=self._attempt)
            raise
        self._emit(
            SandboxOperationState.EXECUTION_STARTED,
            attempt=self._attempt,
            program_sha256=digest,
            source=source_value,
        )
        try:
            result = await self._inner.execute(sandbox_id, source)
        except Exception as error:
            self._fail(
                error,
                attempt=self._attempt,
                program_sha256=digest,
                source=source_value,
            )
            raise
        self._emit(
            SandboxOperationState.EXECUTION_COMPLETED,
            attempt=self._attempt,
            program_sha256=digest,
            source=source_value,
            execution=_execution_preview(
                result, self._sensitive_values, self._configured_secrets
            ),
        )
        return result

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        self._emit(SandboxOperationState.COLLECTION_STARTED, attempt=self._attempt)
        try:
            entries = await self._inner.collect_output(sandbox_id, output_dir)
        except Exception as error:
            self._fail(error, attempt=self._attempt)
            raise
        self._emit(
            SandboxOperationState.COLLECTION_COMPLETED,
            attempt=self._attempt,
            output_count=len(entries),
        )
        return entries

    async def close(self, sandbox_id: SandboxId) -> None:
        self._emit(SandboxOperationState.CLOSING, attempt=self._attempt or None)
        try:
            await self._inner.close(sandbox_id)
        except Exception as error:
            self._fail(error, attempt=self._attempt or None)
            raise
        self._emit(SandboxOperationState.CLOSED, attempt=self._attempt or None)

    def complete(self) -> None:
        self._finish(SandboxOperationState.COMPLETED)

    def cancel(self) -> None:
        self._finish(SandboxOperationState.CANCELLED)

    def fail(self, detail: str | None = None) -> None:
        self._finish(SandboxOperationState.FAILED, failure_detail=detail)

    def _fail(
        self,
        error: Exception,
        *,
        attempt: int | None = None,
        program_sha256: str | None = None,
        source: SandboxPreviewText | None = None,
    ) -> None:
        self._finish(
            SandboxOperationState.FAILED,
            attempt=attempt,
            program_sha256=program_sha256,
            source=source,
            failure_code=type(error).__name__.removesuffix("Error").lower(),
        )

    def _finish(self, state: SandboxOperationState, **fields: Any) -> None:
        if self._finished:
            return
        self._finished = True
        self._emit(state, **fields)

    def _emit(self, state: SandboxOperationState, **fields: Any) -> None:
        if self._finished and state not in {
            SandboxOperationState.FAILED,
            SandboxOperationState.CANCELLED,
            SandboxOperationState.COMPLETED,
        }:
            return
        self._event_count += 1
        self._event_sink(
            SandboxOperationEvent(
                operationId=self.operation_id,
                owner=self.owner,
                state=state,
                generation=max(self._generation, 1),
                **fields,
            )
        )


def _execution_preview(
    result: ExecutionResult,
    sensitive_values: Sequence[str],
    configured_secrets: Sequence[str],
) -> SandboxExecutionPreview:
    return SandboxExecutionPreview(
        exitCode=result.exit_code,
        elapsedSeconds=result.elapsed_seconds,
        timedOut=result.timed_out,
        outputLimited=result.output_limited,
        stdout=_stream_preview(result.stdout, sensitive_values, configured_secrets),
        stderr=_stream_preview(result.stderr, sensitive_values, configured_secrets),
    )


def _source_preview(value: str, configured_secrets: Sequence[str]) -> SandboxPreviewText:
    sanitized = _sanitize(value, configured_secrets)
    return SandboxPreviewText(state="captured", value=sanitized)


def _stream_preview(
    value: str,
    sensitive_values: Sequence[str],
    configured_secrets: Sequence[str],
) -> SandboxPreviewText:
    if not value:
        return SandboxPreviewText(state="empty")
    if any(sensitive in value for sensitive in sensitive_values if sensitive):
        return SandboxPreviewText(state="suppressed")
    if not sandbox_stream_is_safe(value):
        return SandboxPreviewText(state="suppressed")
    return SandboxPreviewText(
        state="captured", value=_sanitize(value[:16_384], configured_secrets)
    )


def _sanitize(value: str, configured_secrets: Sequence[str]) -> str:
    return sanitize_sandbox_text(value, configured_secrets)
