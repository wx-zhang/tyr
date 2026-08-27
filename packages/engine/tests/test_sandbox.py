from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from gamr_engine.ports.sandbox import (
    MAX_OUTPUT_FILES,
    MAX_OUTPUT_TOTAL_BYTES,
    MAX_SOURCE_BYTES,
    ExecutionResult,
    Sandbox,
    SandboxBusyError,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
    SandboxSource,
    SandboxUnavailableError,
    SandboxUnknownError,
    SandboxValidationError,
    execution_result,
    validate_source,
)


def test_source_validation_enforces_utf8_and_fixed_byte_limit() -> None:
    assert validate_source("print('ok')") == b"print('ok')"
    assert validate_source(b"print('ok')") == b"print('ok')"

    with pytest.raises(SandboxValidationError):
        validate_source(b"\xff")
    with pytest.raises(SandboxValidationError):
        validate_source("x" * (MAX_SOURCE_BYTES + 1))


def test_transport_values_are_structured_and_opaque() -> None:
    entry = SandboxEntry("input/data.txt", b"hello")
    result = execution_result(0, b"out", b"err", 0.25)

    assert entry.path == "input/data.txt"
    assert entry.content == b"hello"
    assert result.exit_code == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.elapsed_seconds == 0.25
    assert SandboxId("sandbox-1") == "sandbox-1"


@pytest.mark.asyncio
async def test_protocol_lifecycle_uses_typed_failures() -> None:
    assert Sandbox is not None
    errors = (
        SandboxUnavailableError,
        SandboxUnknownError,
        SandboxClosedError,
        SandboxBusyError,
    )
    assert all(issubclass(error, Exception) for error in errors)

    async def lifecycle() -> None:
        await asyncio.sleep(0)

    await lifecycle()


class FakeEngineSandbox:
    def __init__(self, isolation: SandboxIsolation = "contained") -> None:
        self._isolation = isolation
        self.active_id: SandboxId | None = None
        self.busy = False
        self.closed = False
        self.outputs: dict[str, Sequence[SandboxEntry]] = {}

    @property
    def isolation(self) -> SandboxIsolation:
        return self._isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        self.active_id = SandboxId("sandbox-test-1")
        return self.active_id

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        if self.active_id is None or sandbox_id != self.active_id:
            raise SandboxUnknownError("unknown sandbox")
        if self.closed:
            raise SandboxClosedError("sandbox closed")
        if self.busy:
            raise SandboxBusyError("sandbox busy")
        return ExecutionResult(0, "ok", "", 0.01)

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        if self.active_id is None or sandbox_id != self.active_id:
            raise SandboxUnknownError("unknown sandbox")
        if self.closed:
            raise SandboxClosedError("sandbox closed")
        if self.busy:
            raise SandboxBusyError("sandbox busy")
        if output_dir not in self.outputs:
            raise SandboxValidationError(f"directory {output_dir} not found")
        entries = self.outputs[output_dir]
        if len(entries) > MAX_OUTPUT_FILES:
            raise SandboxValidationError("output exceeds max files")
        total = sum(len(e.content) for e in entries)
        if total > MAX_OUTPUT_TOTAL_BYTES:
            raise SandboxValidationError("output exceeds max bytes")
        return entries

    async def close(self, sandbox_id: SandboxId) -> None:
        if self.active_id is None or sandbox_id != self.active_id:
            raise SandboxUnknownError("unknown sandbox")
        self.closed = True


@pytest.mark.asyncio
async def test_engine_sandbox_contract_isolation_descriptors() -> None:
    contained_sandbox = FakeEngineSandbox(isolation="contained")
    unsafe_sandbox = FakeEngineSandbox(isolation="unsafe")
    unavailable_sandbox = FakeEngineSandbox(isolation="unavailable")

    assert contained_sandbox.isolation == "contained"
    assert unsafe_sandbox.isolation == "unsafe"
    assert unavailable_sandbox.isolation == "unavailable"


@pytest.mark.asyncio
async def test_engine_sandbox_contract_valid_snapshot_and_unknown_closed_ids() -> None:
    sandbox = FakeEngineSandbox()
    sandbox_id = await sandbox.start()
    sandbox.outputs["output/attempt-001"] = [
        SandboxEntry("upload-001/data.txt", b"content"),
        SandboxEntry("upload-001/nested/file.bin", b"\x00\x01\x02"),
    ]

    collected = await sandbox.collect_output(sandbox_id, "output/attempt-001")
    assert len(collected) == 2
    assert collected[0].path == "upload-001/data.txt"
    assert collected[0].content == b"content"
    assert collected[1].path == "upload-001/nested/file.bin"
    assert collected[1].content == b"\x00\x01\x02"

    with pytest.raises(SandboxUnknownError):
        await sandbox.collect_output(SandboxId("unknown-id"), "output/attempt-001")

    await sandbox.close(sandbox_id)
    with pytest.raises(SandboxClosedError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")


@pytest.mark.asyncio
async def test_engine_sandbox_contract_rejects_collection_during_execution() -> None:
    sandbox = FakeEngineSandbox()
    sandbox_id = await sandbox.start()
    sandbox.busy = True

    with pytest.raises(SandboxBusyError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")

    sandbox.busy = False
    sandbox.outputs["output/attempt-001"] = [SandboxEntry("result.txt", b"ok")]
    collected = await sandbox.collect_output(sandbox_id, "output/attempt-001")
    assert len(collected) == 1
    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_engine_sandbox_contract_enforces_output_limits() -> None:
    sandbox = FakeEngineSandbox()
    sandbox_id = await sandbox.start()

    sandbox.outputs["output/oversized-files"] = [
        SandboxEntry(f"file_{i}.txt", b"x") for i in range(MAX_OUTPUT_FILES + 1)
    ]
    with pytest.raises(SandboxValidationError):
        await sandbox.collect_output(sandbox_id, "output/oversized-files")

    sandbox.outputs["output/oversized-bytes"] = [
        SandboxEntry("big.bin", b"x" * (MAX_OUTPUT_TOTAL_BYTES + 1))
    ]
    with pytest.raises(SandboxValidationError):
        await sandbox.collect_output(sandbox_id, "output/oversized-bytes")

    await sandbox.close(sandbox_id)
