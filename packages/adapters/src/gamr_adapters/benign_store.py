from __future__ import annotations

import fcntl
import json
import re
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from gamr_core.benign import TERMINAL, BenignRun, Submission


class BenignStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def directory(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", run_id):
            raise ValueError("Invalid run ID")
        path = self.root / run_id
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Run path escapes storage")
        return path

    def save(self, run: BenignRun) -> None:
        folder = self.directory(run.id)
        folder.mkdir(exist_ok=True, mode=0o700)
        target = folder / "run.json"
        if target.exists() and self.read(run.id).state in TERMINAL:
            raise ValueError("Completed results are immutable")
        self.atomic(target, run.model_dump(mode="json"))

    @staticmethod
    def atomic(path: Path, data: Any) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4()}.tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            temporary.chmod(0o600)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
        temporary.replace(path)

    def read(self, run_id: str) -> BenignRun:
        return BenignRun.model_validate_json(
            (self.directory(run_id) / "run.json").read_text(encoding="utf-8")
        )

    def list_runs(self) -> list[BenignRun]:
        return sorted(
            (self.read(path.parent.name) for path in self.root.glob("*/run.json")),
            key=lambda run: run.created_at,
        )

    def enqueue(self, submission: Submission) -> list[BenignRun]:
        batch_id = str(uuid4())
        runs = [
            BenignRun(
                scenario=scenario,
                batch_id=batch_id,
                concurrency=submission.concurrency,
                action_mode=submission.action_mode,
                confirmed=submission.confirmed,
            )
            for _ in range(submission.repeat)
            for scenario in submission.scenarios
        ]
        for run in runs:
            self.save(run)
        return runs

    def evidence(self, run_id: str, payload: Any) -> str:
        folder = self.directory(run_id) / "evidence"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = f"{uuid4()}.json"
        self.atomic(folder / name, payload)
        return f"evidence/{name}"

    @contextmanager
    def lock(self, name: str) -> Iterator[bool]:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", name):
            raise ValueError("Invalid lock name")
        path = self.root / f".{name}.lock"
        with path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    @contextmanager
    def claim(self, run: BenignRun) -> Iterator[bool]:
        with ExitStack() as stack:
            names = [f"run-{run.id}", *(f"role-{p}" for p in sorted(run.scenario.participants))]
            for name in names:
                if not stack.enter_context(self.lock(name)):
                    yield False
                    return
            yield True
