from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from gamr_core import SandboxOperationEvent, SandboxOperationState
from gamr_engine.ports.sandbox import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
    SandboxSource,
    SandboxValidationError,
)
from gamr_engine.sandbox_preview import ObservedSandbox


class PreviewSandbox(Sandbox):
    def __init__(
        self,
        *,
        starts: list[SandboxId] | None = None,
        executions: list[ExecutionResult] | None = None,
        fail_start: Exception | None = None,
        fail_collect: Exception | None = None,
        fail_close: Exception | None = None,
    ) -> None:
        self.starts = starts or [SandboxId("backend-sandbox-1")]
        self.executions = executions or [ExecutionResult(0, "ok", "", 0.1)]
        self.fail_start = fail_start
        self.fail_collect = fail_collect
        self.fail_close = fail_close
        self.start_count = 0
        self.execute_count = 0
        self.calls: list[str] = []

    @property
    def isolation(self) -> SandboxIsolation:
        return "contained"

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        del entries
        self.calls.append("start")
        if self.fail_start:
            raise self.fail_start
        value = self.starts[min(self.start_count, len(self.starts) - 1)]
        self.start_count += 1
        return value

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        del sandbox_id, source
        self.calls.append("execute")
        result = self.executions[min(self.execute_count, len(self.executions) - 1)]
        self.execute_count += 1
        return result

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        del sandbox_id, output_dir
        self.calls.append("collect")
        if self.fail_collect:
            raise self.fail_collect
        return [SandboxEntry("result.txt", b"ok")]

    async def close(self, sandbox_id: SandboxId) -> None:
        del sandbox_id
        self.calls.append("close")
        if self.fail_close:
            raise self.fail_close


@pytest.mark.asyncio
async def test_observed_sandbox_records_one_logical_session_without_backend_id() -> None:
    events: list[SandboxOperationEvent] = []
    inner = PreviewSandbox()
    sandbox = ObservedSandbox(inner, owner="test-pipeline", event_sink=events.append)

    sandbox_id = await sandbox.start()
    await sandbox.execute(sandbox_id, "print('ok')")
    await sandbox.collect_output(sandbox_id, "output/attempt-001")
    await sandbox.close(sandbox_id)
    sandbox.complete()

    assert inner.calls == ["start", "execute", "collect", "close"]
    assert [event.state for event in events] == [
        SandboxOperationState.REQUESTED,
        SandboxOperationState.READY,
        SandboxOperationState.EXECUTION_STARTED,
        SandboxOperationState.EXECUTION_COMPLETED,
        SandboxOperationState.COLLECTION_STARTED,
        SandboxOperationState.COLLECTION_COMPLETED,
        SandboxOperationState.CLOSING,
        SandboxOperationState.CLOSED,
        SandboxOperationState.COMPLETED,
    ]
    assert len({event.operation_id for event in events}) == 1
    assert all("backend-sandbox" not in event.operation_id for event in events)
    assert events[2].attempt == 1
    assert events[2].source is not None
    assert events[3].execution is not None
    assert events[5].output_count == 1
    assert events[5].output_files is not None
    assert events[5].output_files[0].path == "result.txt"
    assert events[5].output_files[0].content is not None
    assert events[5].output_files[0].content.value == "ok"

@pytest.mark.asyncio
async def test_observed_sandbox_tracks_replacement_generations_and_attempts() -> None:
    events: list[SandboxOperationEvent] = []
    inner = PreviewSandbox(
        starts=[SandboxId("backend-sandbox-1"), SandboxId("backend-sandbox-2")],
        executions=[
            ExecutionResult(None, "", "", 10.0, timed_out=True),
            ExecutionResult(0, "ok", "", 0.1),
        ],
    )
    sandbox = ObservedSandbox(inner, owner="test-pipeline", event_sink=events.append)

    first = await sandbox.start()
    first_result = await sandbox.execute(first, "while True: pass")
    await sandbox.close(first)
    second = await sandbox.start()
    await sandbox.execute(second, "print('ok')")
    await sandbox.collect_output(second, "output/attempt-002")
    await sandbox.close(second)
    sandbox.complete()

    assert first_result.timed_out
    execution_starts = [
        event for event in events if event.state is SandboxOperationState.EXECUTION_STARTED
    ]
    assert [(event.attempt, event.generation) for event in execution_starts] == [(1, 1), (2, 2)]


@pytest.mark.asyncio
async def test_observed_sandbox_records_failures_without_claiming_execution() -> None:
    events: list[SandboxOperationEvent] = []
    sandbox = ObservedSandbox(
        PreviewSandbox(fail_start=SandboxValidationError("invalid input")),
        owner="test-pipeline",
        event_sink=events.append,
    )

    with pytest.raises(SandboxValidationError):
        await sandbox.start()

    assert events[-1].state is SandboxOperationState.FAILED
    assert events[-1].execution is None
    assert events[-1].failure_code == "sandboxvalidation"


@pytest.mark.asyncio
async def test_observed_sandbox_records_collection_and_cleanup_failures() -> None:
    collect_events: list[SandboxOperationEvent] = []
    collect_sandbox = ObservedSandbox(
        PreviewSandbox(fail_collect=SandboxValidationError("bad output")),
        owner="test-pipeline",
        event_sink=collect_events.append,
    )
    sandbox_id = await collect_sandbox.start()
    await collect_sandbox.execute(sandbox_id, "print('ok')")
    with pytest.raises(SandboxValidationError):
        await collect_sandbox.collect_output(sandbox_id, "output/attempt-001")
    assert collect_events[-1].state is SandboxOperationState.FAILED

    close_events: list[SandboxOperationEvent] = []
    close_sandbox = ObservedSandbox(
        PreviewSandbox(fail_close=RuntimeError("cleanup")),
        owner="test-pipeline",
        event_sink=close_events.append,
    )
    close_id = await close_sandbox.start()
    with pytest.raises(RuntimeError):
        await close_sandbox.close(close_id)
    assert close_events[-1].state is SandboxOperationState.FAILED


@pytest.mark.asyncio
async def test_observed_sandbox_cancellation_is_terminal_and_sessions_are_isolated() -> None:
    first_events: list[SandboxOperationEvent] = []
    second_events: list[SandboxOperationEvent] = []
    first = ObservedSandbox(
        PreviewSandbox(), owner="pipeline-a", event_sink=first_events.append
    )
    second = ObservedSandbox(
        PreviewSandbox(), owner="pipeline-a", event_sink=second_events.append
    )

    await asyncio.gather(first.start(), second.start())
    first.cancel()
    second.complete()

    assert first_events[-1].state is SandboxOperationState.CANCELLED
    assert second_events[-1].state is SandboxOperationState.COMPLETED
    assert first.operation_id != second.operation_id


@pytest.mark.asyncio
async def test_observed_sandbox_preserves_sensitive_streams_and_secrets() -> None:
    events: list[SandboxOperationEvent] = []
    inner = PreviewSandbox(
        executions=[ExecutionResult(0, "uploaded-secret", "Bearer api-secret", 0.1)]
    )
    sandbox = ObservedSandbox(
        inner,
        owner="test-pipeline",
        event_sink=events.append,
        sensitive_values=["uploaded-secret"],
        configured_secrets=["api-secret"],
    )

    sandbox_id = await sandbox.start()
    await sandbox.execute(sandbox_id, "print('api-secret')")

    started, completed = events[-2:]
    assert started.source is not None
    assert started.source.value == "print('api-secret')"
    assert completed.execution is not None
    assert completed.execution.stdout.state == "captured"
    assert completed.execution.stdout.value == "uploaded-secret"
    assert completed.execution.stderr.state == "captured"
    assert completed.execution.stderr.value == "Bearer api-secret"


@pytest.mark.asyncio
async def test_observed_sandbox_preserves_paths_and_bounds_streams() -> None:
    events: list[SandboxOperationEvent] = []
    inner = PreviewSandbox(
        executions=[ExecutionResult(0, "/home/alice/secret\n" + "x" * 20_000, "", 0.1)]
    )
    sandbox = ObservedSandbox(inner, owner="test-pipeline", event_sink=events.append)

    sandbox_id = await sandbox.start()
    await sandbox.execute(sandbox_id, "print('ok')")

    execution = events[-1].execution
    assert execution is not None
    assert execution.stdout.state == "captured"
    assert execution.stdout.value is not None
    assert execution.stdout.value.startswith("/home/alice/secret\n")
    assert len(execution.stdout.value) == 16_384
    assert execution.stderr.state == "empty"


@pytest.mark.asyncio
async def test_observed_sandbox_captures_bounded_safe_diagnostic_output() -> None:
    events: list[SandboxOperationEvent] = []
    sandbox = ObservedSandbox(
        PreviewSandbox(executions=[ExecutionResult(1, "syntax error", "", 0.1)]),
        owner="test-pipeline",
        event_sink=events.append,
    )

    sandbox_id = await sandbox.start()
    await sandbox.execute(sandbox_id, "raise SystemExit(1)")

    execution = events[-1].execution
    assert execution is not None
    assert execution.stdout.state == "captured"
    assert execution.stdout.value == "syntax error"
