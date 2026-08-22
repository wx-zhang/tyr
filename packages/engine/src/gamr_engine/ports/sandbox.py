from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NewType, Protocol

MAX_SOURCE_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_OUTPUT_FILES = 256
MAX_OUTPUT_TOTAL_BYTES = 64 * 1024 * 1024
MAX_ATTACHMENT_FILES = 256
MAX_ATTACHMENT_BYTES = 64 * 1024 * 1024
MAX_EXECUTION_SECONDS = 10.0
MAX_WORKSPACE_BYTES = 128 * 1024 * 1024
MAX_MEMORY_BYTES = 256 * 1024 * 1024
MAX_PROCESSES = 64

SandboxId = NewType("SandboxId", str)
type SandboxSource = str | bytes
type SandboxIsolation = Literal["contained", "unsafe", "unavailable"]


class SandboxError(RuntimeError):
    """Base error for sandbox lifecycle failures."""


class SandboxValidationError(SandboxError, ValueError):
    """The caller supplied source or attachment data outside the contract."""


class SandboxUnavailableError(SandboxError):
    """The selected backend cannot create a sandbox."""


class SandboxUnknownError(SandboxError):
    """The sandbox ID does not belong to this process."""


class SandboxClosedError(SandboxError):
    """The sandbox ID was closed and cannot execute again."""


class SandboxBusyError(SandboxError):
    """The sandbox already has an active execution."""


class SandboxInfrastructureError(SandboxError):
    """The backend failed outside the executed Python process."""


@dataclass(frozen=True, slots=True)
class SandboxEntry:
    path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    exit_code: int | None
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False
    output_limited: bool = False

    def as_dict(self) -> dict[str, int | float | str | bool | None]:
        return {
            "exitCode": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "elapsedSeconds": self.elapsed_seconds,
            "timedOut": self.timed_out,
            "outputLimited": self.output_limited,
        }


def validate_source(source: SandboxSource) -> bytes:
    try:
        if isinstance(source, str):
            encoded = source.encode("utf-8")
        elif isinstance(source, bytes):
            encoded = source
        else:
            raise TypeError
        encoded.decode("utf-8")
    except (TypeError, UnicodeError) as error:
        raise SandboxValidationError("source must be valid UTF-8") from error
    if len(encoded) > MAX_SOURCE_BYTES:
        raise SandboxValidationError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    return encoded


def execution_result(
    exit_code: int | None,
    stdout: bytes,
    stderr: bytes,
    elapsed_seconds: float,
    *,
    timed_out: bool = False,
    output_limited: bool = False,
) -> ExecutionResult:
    return ExecutionResult(
        exit_code,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        elapsed_seconds,
        timed_out,
        output_limited,
    )


class Sandbox(Protocol):
    @property
    def isolation(self) -> SandboxIsolation:
        """Declared isolation level of this backend."""

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        """Create an ephemeral sandbox and return its process-local ID."""

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        """Run one fresh Python process in an existing sandbox."""

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        """Collect bounded regular files below a workspace output directory."""

    async def close(self, sandbox_id: SandboxId) -> None:
        """Close a sandbox; repeating close is safe."""
