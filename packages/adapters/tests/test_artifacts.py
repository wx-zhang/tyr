import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from gamr_adapters.artifacts.evidence import BundleNormalizer
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore, redact_payload
from gamr_core import (
    CaseResult,
    Evidence,
    ExecutionOutcome,
    ExperimentConfig,
    ResultSummary,
    RunResult,
    SecurityVerdict,
    TaskReference,
)


def test_redact_payload_handles_keys_headers_and_configured_values() -> None:
    payload = {
        "Authorization": "Bearer abc123",
        "nested": {"apiKey": "key-value", "message": "token=key-value"},
        "text": "Bearer abc123 and key-value",
    }
    redacted = redact_payload(payload, ["key-value"])
    assert redacted == {
        "Authorization": "[REDACTED]",
        "nested": {"apiKey": "[REDACTED]", "message": "token=[REDACTED]"},
        "text": "Bearer [REDACTED] and [REDACTED]",
    }


def test_raw_artifact_is_confined_and_redacted(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr", secrets=["super-secret"])
    path = store.write_raw(
        "run-1",
        "turn-1",
        {"headers": {"Authorization": "Bearer super-secret"}, "body": "super-secret"},
    )
    assert "super-secret" not in Path(path).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        store.write_json("../outside.json", {"ok": True})


def test_artifact_store_lists_persisted_run_bundles(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr")
    store.write_json("runs/run-b/run.json", {"id": "run-b"})
    store.write_json("runs/run-a/run.json", {"id": "run-a"})

    assert store.list_run_ids() == ["run-a", "run-b"]


def test_result_finalization_preserves_existing_raw_diagnostics(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr", secrets=["super-secret"])
    store.write_raw("run-1", "turn-1", {"diagnostic": "captured", "token": "super-secret"})
    raw_path = tmp_path / ".gamr" / "runs" / "run-1" / "raw" / "turn-1.json"
    before = raw_path.read_bytes()
    result = RunResult(
        runId="run-1",
        task=TaskReference(id="demo", version="1.0", digest="sha256:demo"),
        startedAt=datetime(2026, 8, 8, 10, tzinfo=UTC),
        outcome=ExecutionOutcome.COMPLETED,
        configuration=ExperimentConfig(),
        summary=ResultSummary(vulnerable=0, protected=1, inconclusive=0),
        cases=[
            CaseResult(
                scenarioId="case-1",
                outcome=ExecutionOutcome.COMPLETED,
                verdict=SecurityVerdict.PROTECTED,
                summary="Protected",
                evidence=[Evidence(turnId="turn-1", artifact="raw/turn-1.json")],
            )
        ],
        findings=[],
        errors=[],
    )

    store.write_result("run-1", result)

    assert raw_path.read_bytes() == before
    assert "captured" in raw_path.read_text(encoding="utf-8")


def test_write_result_marks_existing_run_json_terminal(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr")
    store.write_json(
        "runs/run-1/run.json",
        {
            "schemaVersion": "1.0",
            "id": "run-1",
            "source": "cli",
            "task": "tasks/demo",
            "state": "running",
            "configuration": {"actionMode": "read_only"},
            "createdAt": "2026-08-08T10:00:00Z",
            "updatedAt": "2026-08-08T10:00:00Z",
        },
    )
    result = RunResult(
        runId="run-1",
        task=TaskReference(id="demo", version="1.0", digest="sha256:demo"),
        startedAt=datetime(2026, 8, 8, 10, tzinfo=UTC),
        outcome=ExecutionOutcome.BLOCKED,
        configuration=ExperimentConfig(),
        summary=ResultSummary(vulnerable=0, protected=0, inconclusive=0),
        cases=[],
        findings=[],
        errors=["discovery failed"],
    )

    store.write_result("run-1", result)

    document = json.loads(
        (tmp_path / ".gamr" / "runs" / "run-1" / "run.json").read_text(encoding="utf-8")
    )
    assert document["state"] == "completed"
    assert document["resultPath"] == "result.json"
    assert document["finishedAt"]
    assert document["updatedAt"] == document["finishedAt"]


def test_confined_redacted_evidence_reads_reject_escape_and_directories(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr")
    store.write_raw("run-1", "turn-1", {"message": "safe"})

    assert store.read_evidence("run-1", "raw/turn-1.json")["message"] == "safe"
    with pytest.raises(ValueError, match="escapes"):
        store.read_evidence("run-1", "../../outside.json")
    with pytest.raises(ValueError, match="run root"):
        store.read_evidence("run-1", "../checkpoint.json")


def test_configured_secret_stays_out_of_legacy_search_graph_and_download_views(
    tmp_path: Path,
) -> None:
    secret = "configured-secret"
    store = FilesystemArtifactStore(tmp_path / ".gamr", secrets=[secret])
    store.write_json("runs/run-1/run.json", {"runId": "run-1", "searchField": secret})
    raw_path = store.write_raw(
        "run-1",
        "evidence-1",
        {
            "summary": f"Search {secret}",
            "graphLabel": f"Bearer {secret}",
            "detail": secret,
        },
    )

    assert secret not in Path(raw_path).read_text(encoding="utf-8")
    assert secret not in json.dumps(store.read_evidence("run-1", "raw/evidence-1.json"))
    assert secret not in store.read_evidence_download("run-1", "raw/evidence-1.json").decode()

    legacy = tmp_path / "legacy"
    (legacy / "raw").mkdir(parents=True)
    (legacy / "run.json").write_text(json.dumps({"runId": "legacy-run"}), encoding="utf-8")
    (legacy / "events.jsonl").write_text(
        json.dumps(
            {
                "sequence": 1,
                "eventType": "model.response",
                "payload": {
                    "summary": f"Legacy search {secret}",
                    "graphLabel": secret,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (legacy / "raw" / "legacy.json").write_text(
        json.dumps({"summary": f"Legacy detail {secret}"}), encoding="utf-8"
    )

    normalized = BundleNormalizer(secrets=[secret]).normalize_bundle(legacy, run_id="legacy-run")

    assert secret not in json.dumps(normalized.activities, default=str)
    assert secret not in json.dumps(normalized.evidence, default=str)
