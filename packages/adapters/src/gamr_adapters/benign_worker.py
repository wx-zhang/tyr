from __future__ import annotations

import asyncio
from collections import Counter

from gamr_core.benign import BenignRun
from gamr_engine.benign import run_scenario

from .benign_config import BenignSettings
from .benign_store import BenignStore
from .benign_tyr import LiveBenignRuntime


class BenignWorker:
    def __init__(self, settings: BenignSettings) -> None:
        self.settings = settings
        self.store = BenignStore(settings.root)
        self.active: dict[str, asyncio.Task[None]] = {}

    async def execute(self, run: BenignRun) -> None:
        with self.store.claim(run) as acquired:
            if not acquired:
                return
            run = self.store.read(run.id)
            marker = self.store.directory(run.id) / "resume.json"
            if run.state == "pending" and marker.exists():
                self.store.evidence(
                    run.id, {"type": "resume", "previous": run.model_dump(mode="json")}
                )
                target = run.phase if run.phase in run.checkpoints else "stimulus"
                run.observations.pop(target, None)
                if target == "stimulus":
                    for key in list(run.checkpoints):
                        if key.startswith("verify."):
                            run.observations.pop(key, None)
                            generation = run.checkpoints[key].get("generation", 0) + 1
                            run.checkpoints[key] = {"generation": generation}
                run.assessment = None
                marker.unlink()
            try:
                await run_scenario(run, LiveBenignRuntime(self.store, self.settings))
            except asyncio.CancelledError:
                run.state = "pending"
                run.summary = (
                    "Worker stopped. Remote work may continue. Resume polls saved operations."
                )
                self.store.save(run)
                raise

    def resume(self, run_id: str) -> None:
        with self.store.lock(f"run-{run_id}") as acquired:
            if not acquired:
                raise ValueError("Run is still active")
            run = self.store.read(run_id)
            if run.state != "pending":
                raise ValueError("Only pending runs can resume")
            self.store.atomic(self.store.directory(run_id) / "resume.json", {"requested": True})

    async def tick(self) -> None:
        for run_id, task in list(self.active.items()):
            if task.done():
                task.result()
                del self.active[run_id]
        runs = self.store.list_runs()
        occupied: set[str] = set()
        counts: Counter[str] = Counter()
        for run in runs:
            if run.id in self.active or run.state == "pending":
                occupied.update(run.scenario.participants)
            if run.id in self.active:
                counts[run.batch_id] += 1
        for run in runs:
            if len(self.active) >= self.settings.workers:
                break
            if run.id in self.active:
                continue
            resume = (
                run.state == "pending" and (self.store.directory(run.id) / "resume.json").exists()
            )
            if run.state != "queued" and not resume:
                continue
            if counts[run.batch_id] >= run.concurrency:
                continue
            peers = set(run.scenario.participants)
            if not resume and peers & occupied:
                continue
            if resume and any(
                other.id != run.id
                and (other.id in self.active or other.state == "pending")
                and peers.intersection(other.scenario.participants)
                for other in runs
            ):
                continue
            occupied.update(peers)
            counts[run.batch_id] += 1
            self.active[run.id] = asyncio.create_task(self.execute(run))

    async def serve(self) -> None:
        with self.store.lock("worker") as acquired:
            if not acquired:
                raise ValueError("A benign worker is already running for this storage root")
            for run in self.store.list_runs():
                if run.state == "running":
                    run.state = "pending"
                    run.summary = (
                        "Worker interrupted; explicit resume required. No request replayed."
                    )
                    self.store.save(run)
            try:
                while True:
                    await self.tick()
                    await asyncio.sleep(1)
            finally:
                for task in self.active.values():
                    task.cancel()
                await asyncio.gather(*self.active.values(), return_exceptions=True)
