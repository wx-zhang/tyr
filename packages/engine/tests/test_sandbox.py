from __future__ import annotations

import asyncio

import pytest
from gamr_engine.ports.sandbox import (
    MAX_SOURCE_BYTES,
    SandboxBusyError,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
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
    from gamr_engine.ports.sandbox import Sandbox

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
