from __future__ import annotations

import asyncio
from collections.abc import Sequence

from gamr_engine.decoder_capacity import DecoderCapacityGate
from gamr_engine.ports.sandbox import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
    SandboxSource,
)


class CapacitySandbox(Sandbox):
    def __init__(self, inner: Sandbox, gate: DecoderCapacityGate) -> None:
        self._inner = inner
        self._gate = gate
        self._held_sandboxes: set[SandboxId] = set()

    @property
    def isolation(self) -> SandboxIsolation:
        return self._inner.isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] | None = None
        if self._gate._active >= self._gate._capacity:
            waiter = loop.create_future()
            self._gate._waiters.append(waiter)
            try:
                await waiter
            except BaseException:
                if waiter in self._gate._waiters:
                    self._gate._waiters.remove(waiter)
                elif waiter.done() and not waiter.cancelled():
                    self._gate._release()
                raise
        else:
            self._gate._active += 1

        try:
            sid = await self._inner.start(entries)
            self._held_sandboxes.add(sid)
            return sid
        except BaseException:
            self._gate._release()
            raise

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        return await self._inner.execute(sandbox_id, source)

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        return await self._inner.collect_output(sandbox_id, output_dir)

    async def close(self, sandbox_id: SandboxId) -> None:
        try:
            await self._inner.close(sandbox_id)
        finally:
            if sandbox_id in self._held_sandboxes:
                self._held_sandboxes.remove(sandbox_id)
                self._gate._release()
