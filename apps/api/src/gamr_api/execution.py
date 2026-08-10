from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from gamr_core import RunState

from .registry import JsonRegistry

RunExecutor = Callable[[str], Coroutine[Any, Any, str]]


class RunTaskManager:
    def __init__(
        self,
        registry: JsonRegistry,
        execute: RunExecutor,
        *,
        max_concurrent_runs: int = 3,
    ) -> None:
        if max_concurrent_runs < 1:
            raise ValueError("max_concurrent_runs must be at least one")
        self.registry = registry
        self.execute = execute
        self.max_concurrent_runs = max_concurrent_runs
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending: set[str] = set()
        self._active: dict[str, asyncio.Task[str]] = {}
        self._consumers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        self.registry.refresh()
        self.registry.interrupt_service_runs()
        self._consumers = [
            asyncio.create_task(self._consume(), name=f"gamr-run-slot-{index + 1}")
            for index in range(self.max_concurrent_runs)
        ]

    async def submit(self, run_id: str) -> None:
        run = self.registry.get_run(run_id)
        if run is None or run.state is not RunState.QUEUED:
            raise ValueError("only queued runs can be submitted")
        if run_id in self._pending or run_id in self._active:
            return
        self._pending.add(run_id)
        await self._queue.put(run_id)

    async def cancel(self, run_id: str) -> bool:
        run = self.registry.get_run(run_id)
        if run is None:
            return False
        if run.state in {
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.INTERRUPTED,
        }:
            return True
        self._pending.discard(run_id)
        self.registry.set_state(run, RunState.CANCELLED, event_type="run.cancelled")
        task = self._active.get(run_id)
        if task is not None:
            task.cancel()
        return True

    async def join(self) -> None:
        await self._queue.join()

    async def shutdown(self) -> None:
        for run_id in list(self._pending):
            run = self.registry.get_run(run_id)
            if run is not None and run.state is RunState.QUEUED:
                self.registry.set_state(run, RunState.INTERRUPTED, event_type="run.interrupted")
        self._pending.clear()
        for run_id, task in list(self._active.items()):
            run = self.registry.get_run(run_id)
            if run is not None and run.state not in {
                RunState.COMPLETED,
                RunState.FAILED,
                RunState.CANCELLED,
                RunState.INTERRUPTED,
            }:
                self.registry.set_state(run, RunState.INTERRUPTED, event_type="run.interrupted")
            task.cancel()
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)
        for consumer in self._consumers:
            consumer.cancel()
        if self._consumers:
            await asyncio.gather(*self._consumers, return_exceptions=True)
        self._consumers.clear()

    async def _consume(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                if run_id not in self._pending:
                    continue
                self._pending.remove(run_id)
                run = self.registry.get_run(run_id)
                if run is None or run.state is not RunState.QUEUED:
                    continue
                self.registry.set_state(run, RunState.PREPARING)
                self.registry.set_state(run, RunState.DISCOVERING)
                self.registry.set_state(run, RunState.RUNNING)
                task: asyncio.Task[str] = asyncio.create_task(
                    self.execute(run_id), name=f"gamr-run-{run_id}"
                )
                self._active[run_id] = task
                try:
                    result_path = await task
                except asyncio.CancelledError:
                    current = self.registry.get_run(run_id)
                    if current is not None and current.state not in {
                        RunState.CANCELLED,
                        RunState.INTERRUPTED,
                    }:
                        self.registry.set_state(
                            current, RunState.INTERRUPTED, event_type="run.interrupted"
                        )
                    continue
                except Exception as error:
                    current = self.registry.get_run(run_id)
                    if current is not None:
                        self.registry.set_state(
                            current,
                            RunState.FAILED,
                            event_type="run.failed",
                            error_summary=f"{type(error).__name__}: {error}",
                        )
                    continue
                current = self.registry.get_run(run_id)
                if current is None or current.state is not RunState.RUNNING:
                    continue
                self.registry.set_result(current, result_path)
                self.registry.set_state(current, RunState.EVALUATING)
                self.registry.set_state(current, RunState.REPORTING)
                self.registry.set_state(current, RunState.COMPLETED)
            finally:
                self._active.pop(run_id, None)
                self._queue.task_done()
