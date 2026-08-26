from __future__ import annotations

import json
import os
import re
import shutil
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, cast

from gamr_core import RunResult

from .finalizer import finalize_result
from .redaction import redact_payload
from .scientist_scenarios import ScientistScenarioCatalog

__all__ = [
    "FilesystemArtifactStore",
    "MAX_INTERACTIVE_EVIDENCE_BYTES",
    "finalize_result",
    "redact_payload",
]

MAX_INTERACTIVE_EVIDENCE_BYTES = 64 * 1024


class FilesystemArtifactStore:
    _activity_locks: dict[str, RLock] = defaultdict(RLock)

    def __init__(self, root: str | Path = ".gamr", *, secrets: Iterable[str] = ()) -> None:
        self.root = Path(root)
        self.secrets = tuple(secrets)

    def _run_root(self, run_id: str, *, create: bool = True) -> Path:
        path = (self.root / "runs" / run_id).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("run path escapes artifact root")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def delete_run(self, run_id: str) -> None:
        run_root = self._run_root(run_id, create=False)
        ScientistScenarioCatalog(self.root).delete_run_markers(run_id)
        if run_root.is_dir():
            shutil.rmtree(run_root)

    def list_run_ids(self) -> list[str]:
        runs_root = (self.root / "runs").resolve()
        if not runs_root.is_dir():
            return []
        return sorted(
            path.name
            for path in runs_root.iterdir()
            if path.is_dir() and (path / "run.json").is_file()
        )

    def is_scientist_scenario_archived(self, run_id: str, artifact_id: str) -> bool:
        return ScientistScenarioCatalog(self.root).is_scientist_scenario_archived(
            run_id, artifact_id
        )

    def _safe_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("artifact path escapes artifact root")
        return path

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> str:
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_json(path, redact_payload(payload, self.secrets))
        return str(path)

    def write_raw(self, run_id: str, turn_id: str, payload: dict[str, Any]) -> str:
        run_root = self._run_root(run_id, create=False)
        path = (run_root / "raw" / f"{turn_id}.json").resolve()
        if run_root not in path.parents:
            raise ValueError("raw artifact path escapes run root")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_json(path, redact_payload(payload, self.secrets))
        return str(path)

    def _evidence_path(self, run_id: str, relative_path: str) -> Path:
        run_root = self._run_root(run_id, create=False)
        path = (run_root / relative_path).resolve()
        if run_root not in path.parents:
            raise ValueError("evidence path escapes run root")
        return path

    def read_evidence(self, run_id: str, relative_path: str) -> Any:
        path = self._evidence_path(run_id, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("evidence is malformed JSON") from error
        return redact_payload(payload, self.secrets)

    def read_json(self, run_id: str, relative_path: str) -> dict[str, Any]:
        payload = self.read_evidence(run_id, relative_path)
        if not isinstance(payload, dict):
            raise ValueError(f"{relative_path} is not a JSON object")
        return payload

    def read_transcript(self, run_id: str) -> list[dict[str, Any]]:
        run_root = self._run_root(run_id, create=False)
        path = run_root / "transcript.jsonl"
        if not path.is_file():
            return []
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = redact_payload(json.loads(line), self.secrets)
                if isinstance(value, dict):
                    records.append(value)
        return records

    def read_evidence_bytes(self, run_id: str, relative_path: str) -> bytes:
        return json.dumps(
            self.read_evidence(run_id, relative_path),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

    def evidence_size(self, run_id: str, relative_path: str) -> int:
        path = self._evidence_path(run_id, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.stat().st_size

    def read_evidence_content(
        self,
        run_id: str,
        relative_path: str,
        *,
        max_bytes: int = MAX_INTERACTIVE_EVIDENCE_BYTES,
    ) -> Any:
        if self.evidence_size(run_id, relative_path) > max_bytes:
            raise OverflowError("evidence exceeds the interactive detail limit")
        return self.read_evidence(run_id, relative_path)

    @staticmethod
    def safe_evidence_filename(run_id: str, evidence_id: str) -> str:
        safe_run = re.sub(r"[^A-Za-z0-9_-]", "-", run_id)[:64] or "run"
        safe_evidence = re.sub(r"[^A-Za-z0-9_-]", "-", evidence_id)[:64] or "evidence"
        return f"{safe_run}-{safe_evidence}.json"

    def read_evidence_download(self, run_id: str, relative_path: str) -> bytes:
        return self.read_evidence_bytes(run_id, relative_path)

    def write_report(self, run_id: str, content: str) -> str:
        run_root = self._run_root(run_id)
        path = self._safe_path(str(Path("runs") / run_id / "report.md"))
        if run_root not in path.parents:
            raise ValueError("report path escapes run root")
        path.write_text(redact_payload(content, self.secrets), encoding="utf-8")
        return str(path)

    def append_event(self, run_id: str, payload: dict[str, Any]) -> str:
        run_root = self._run_root(run_id)
        path = run_root / "events.jsonl"
        sequence = 0
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                sequence = sum(1 for _ in handle)
        record = dict(payload)
        record["sequence"] = sequence + 1
        self._append_jsonl(path, [record])
        return str(path)

    def append_activity(self, payload: dict[str, Any]) -> str:
        run_id = payload.get("runId") or payload.get("run_id")
        activity_id = payload.get("id")
        if not isinstance(run_id, str) or not run_id or not isinstance(activity_id, str):
            raise ValueError("canonical activity requires runId and id")
        run_root = self._run_root(run_id)
        path = run_root / "activity.jsonl"
        with self._activity_locks[str(path)]:
            expected = redact_payload(payload, self.secrets)
            if path.exists():
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        existing = json.loads(line)
                        if existing.get("id") == activity_id:
                            if existing != expected:
                                raise ValueError(
                                    "activity ID already exists with different content"
                                )
                            return str(path)
            self._append_jsonl(path, [expected])
        return str(path)

    def read_activity_records(self, run_id: str) -> list[dict[str, Any]]:
        run_root = self._run_root(run_id, create=False)
        path = run_root / "activity.jsonl"
        if not path.is_file():
            return []
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def write_checkpoint(self, run_id: str, payload: dict[str, Any]) -> str:
        run_root = self._run_root(run_id)
        path = run_root / "checkpoint.json"
        self._atomic_json(path, redact_payload(payload, self.secrets))
        return str(path)

    def write_case_checkpoint(self, run_id: str, case_id: str, payload: dict[str, Any]) -> str:
        if "/" in case_id or "\\" in case_id or ".." in case_id:
            raise ValueError("case checkpoint path escapes run root")
        run_root = self._run_root(run_id)
        safe_case = re.sub(r"[^A-Za-z0-9_-]", "-", case_id)[:128] or "case"
        case_dir = (run_root / "checkpoints" / "cases").resolve()
        path = (case_dir / f"{safe_case}.json").resolve()
        if run_root not in path.parents or case_dir not in path.parents:
            raise ValueError("case checkpoint path escapes run root")
        case_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_json(path, redact_payload(payload, self.secrets))
        return str(path)

    def read_checkpoint(self, run_id: str) -> dict[str, Any]:
        run_root = self._run_root(run_id, create=False)
        path = run_root / "checkpoint.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("checkpoint is malformed JSON") from error
        return cast(dict[str, Any], redact_payload(payload, self.secrets))

    def read_case_checkpoint(self, run_id: str, case_id: str) -> dict[str, Any]:
        run_root = self._run_root(run_id, create=False)
        safe_case = re.sub(r"[^A-Za-z0-9_-]", "-", case_id)[:128] or "case"
        path = (run_root / "checkpoints" / "cases" / f"{safe_case}.json").resolve()
        if run_root not in path.parents:
            raise ValueError("case checkpoint path escapes run root")
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("case checkpoint is malformed JSON") from error
        return cast(dict[str, Any], redact_payload(payload, self.secrets))

    def append_transcript(self, run_id: str, records: list[dict[str, Any]]) -> str:
        run_root = self._run_root(run_id)
        path = run_root / "transcript.jsonl"
        self._append_jsonl(path, records)
        return str(path)

    def write_result(
        self,
        run_id: str,
        result: RunResult,
        task_snapshot: dict[str, object] | None = None,
    ) -> str:
        return finalize_result(self, run_id, result, task_snapshot=task_snapshot)

    def _atomic_json(self, path: Path, payload: dict[str, Any]) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)

    def _write_jsonl(self, path: Path, records: list[dict[str, object]]) -> None:
        path.write_text("", encoding="utf-8")
        self._append_jsonl(path, records)

    def _append_jsonl(self, path: Path, records: list[dict[str, object]]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(redact_payload(record, self.secrets), ensure_ascii=False))
                handle.write("\n")
