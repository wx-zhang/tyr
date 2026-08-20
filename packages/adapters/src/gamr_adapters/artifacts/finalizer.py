from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gamr_core import ExecutionOutcome, RunResult, RunState

from .redaction import redact_payload


def terminal_run_state(outcome: ExecutionOutcome) -> RunState:
    if outcome is ExecutionOutcome.CANCELLED:
        return RunState.CANCELLED
    if outcome is ExecutionOutcome.INTERRUPTED:
        return RunState.INTERRUPTED
    if outcome in {ExecutionOutcome.FAILED, ExecutionOutcome.ERROR}:
        return RunState.FAILED
    return RunState.COMPLETED


def mark_run_document_terminal(
    run_path: Path,
    *,
    terminal_state: RunState,
    finished_at: str,
    secrets: tuple[str, ...],
    atomic_json_fn: Any,
) -> None:
    try:
        document = json.loads(run_path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return
    if not isinstance(document, dict):
        return
    if "state" in document or "schemaVersion" in document:
        document["state"] = terminal_state.value
        document["resultPath"] = document.get("resultPath") or "result.json"
        document["updatedAt"] = finished_at
        document["finishedAt"] = finished_at
    else:
        document["status"] = terminal_state.value
    atomic_json_fn(run_path, redact_payload(document, secrets))


def finalize_result(
    store: Any,
    run_id: str,
    result: RunResult,
    task_snapshot: dict[str, object] | None = None,
) -> str:
    run_root = store._run_root(run_id)
    payload = result.model_dump(by_alias=True, exclude_none=True, mode="json")
    payload["$schema"] = "../../../schemas/run-result.schema.json"
    store._atomic_json(run_root / "result.json", redact_payload(payload, store.secrets))
    run_path = run_root / "run.json"
    terminal_state = terminal_run_state(result.outcome)
    finished_at = (
        result.finished_at.isoformat().replace("+00:00", "Z")
        if result.finished_at is not None
        else payload.get("finishedAt")
    )
    if not isinstance(finished_at, str) or not finished_at:
        finished_at = payload.get("startedAt") or ""
    if run_path.exists():
        mark_run_document_terminal(
            run_path,
            terminal_state=terminal_state,
            finished_at=str(finished_at),
            secrets=store.secrets,
            atomic_json_fn=store._atomic_json,
        )
    else:
        store._atomic_json(
            run_path,
            redact_payload({"runId": run_id, "status": result.outcome.value}, store.secrets),
        )
    store._atomic_json(
        run_root / "task.snapshot.json",
        redact_payload(task_snapshot or {"task": payload["task"]}, store.secrets),
    )
    store.write_checkpoint(run_id, {"runId": run_id, "status": result.outcome.value})
    store.append_event(
        run_id,
        {"runId": run_id, "eventType": "run.completed", "status": result.outcome.value},
    )
    transcript_path = run_root / "transcript.jsonl"
    if not transcript_path.exists():
        store.append_transcript(
            run_id,
            [{"scenarioId": case.scenario_id, "summary": case.summary} for case in result.cases],
        )
    for case in result.cases:
        for evidence in case.evidence:
            evidence_path = (run_root / evidence.artifact).resolve()
            if run_root not in evidence_path.parents:
                raise ValueError("evidence path escapes run root")
            if not evidence_path.exists():
                evidence_path.parent.mkdir(parents=True, exist_ok=True)
    return str(run_root / "result.json")
