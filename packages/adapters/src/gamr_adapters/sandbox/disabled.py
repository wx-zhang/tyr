from __future__ import annotations

from collections.abc import Sequence

from gamr_engine.ports import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
    SandboxSource,
    SandboxUnavailableError,
)


class DisabledSandbox(Sandbox):
    @property
    def isolation(self) -> SandboxIsolation:
        return "unavailable"

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        del entries
        raise SandboxUnavailableError("Python sandboxing is disabled")

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        del sandbox_id, source
        raise SandboxUnavailableError("Python sandboxing is disabled")

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        del sandbox_id, output_dir
        raise SandboxUnavailableError("Python sandboxing is disabled")

    async def close(self, sandbox_id: SandboxId) -> None:
        del sandbox_id
