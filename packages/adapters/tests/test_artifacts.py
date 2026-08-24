import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from gamr_adapters.artifacts.evidence import BundleNormalizer
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore, redact_payload
from gamr_core import (
    CaseResult,
    ContentOverlapResult,
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


def test_redact_payload_bounds_and_sanitizes_sandbox_event() -> None:
    redacted = redact_payload(
        {
            "sandboxEvent": {
                "operationId": "operation-1",
                "state": "execution_completed",
                "generation": 1,
                "source": {"state": "captured", "value": "open('/home/alice/input')"},
                "execution": {
                    "exitCode": 0,
                    "elapsedSeconds": 0.1,
                    "stdout": {"state": "captured", "value": "Bearer configured-secret"},
                    "stderr": {"state": "empty"},
                },
            }
        },
        ["configured-secret"],
    )

    event = redacted["sandboxEvent"]
    assert event["source"]["value"] == "open('[REDACTED_PATH]')"
    assert event["execution"]["stdout"] == {
        "state": "captured",
        "value": "Bearer [REDACTED]",
    }


def test_redaction_keeps_content_overlap_summary_schema_valid(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr", secrets=["s"])
    store.write_json(
        "runs/run-1/case-results/case-1.json",
        {
            "contentOverlap": {
                "status": "not_found",
                "assessmentStatus": "valid",
                "summary": "x" * 599 + "s",
                "matches": [],
            }
        },
    )

    payload = json.loads(
        (tmp_path / ".gamr" / "runs" / "run-1" / "case-results" / "case-1.json").read_text(
            encoding="utf-8"
        )
    )
    overlap = ContentOverlapResult.model_validate(payload["contentOverlap"])

    summary = overlap.summary or ""
    full_summary = overlap.full_summary or ""
    assert len(summary) == 600
    assert len(full_summary) == 609
    assert "s" not in summary
    assert "s" not in full_summary


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


def test_per_case_checkpoint_writes_and_confinement(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr", secrets=["secret-tok"])
    path = store.write_case_checkpoint(
        "run-1",
        "case-1",
        {"caseId": "case-1", "userToken": "secret-tok", "turn": 2},
    )
    assert "secret-tok" not in Path(path).read_text(encoding="utf-8")
    assert "[REDACTED]" in Path(path).read_text(encoding="utf-8")
    assert (
        tmp_path / ".gamr" / "runs" / "run-1" / "checkpoints" / "cases" / "case-1.json"
    ).is_file()

    with pytest.raises(ValueError, match="escapes"):
        store.write_case_checkpoint("run-1", "../escape", {"ok": True})


def test_read_checkpoint_supports_legacy_and_per_case(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr")
    # Legacy singleton checkpoint
    store.write_checkpoint("run-legacy", {"phase": "discovery", "turn": 1})
    legacy = store.read_checkpoint("run-legacy")
    assert legacy == {"phase": "discovery", "turn": 1}

    # Per-case checkpoints
    store.write_case_checkpoint("run-1", "case-a", {"caseId": "case-a", "turn": 1})
    store.write_case_checkpoint("run-1", "case-b", {"caseId": "case-b", "turn": 2})

    case_a = store.read_case_checkpoint("run-1", "case-a")
    assert case_a == {"caseId": "case-a", "turn": 1}
    case_b = store.read_case_checkpoint("run-1", "case-b")
    assert case_b == {"caseId": "case-b", "turn": 2}


def test_monotonic_activities_and_interleaved_append(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / ".gamr")
    # Append transcript records interleaved
    store.append_transcript("run-1", [{"caseId": "case-1", "role": "user", "content": "hello 1"}])
    store.append_transcript("run-1", [{"caseId": "case-2", "role": "user", "content": "hello 2"}])
    store.append_transcript(
        "run-1", [{"caseId": "case-1", "role": "assistant", "content": "reply 1"}]
    )

    transcript = store.read_transcript("run-1")
    assert len(transcript) == 3
    assert [r["caseId"] for r in transcript] == ["case-1", "case-2", "case-1"]

    # Append events
    store.append_event("run-1", {"caseId": "case-1", "type": "turn.completed"})
    store.append_event("run-1", {"caseId": "case-2", "type": "turn.completed"})
    events_file = tmp_path / ".gamr" / "runs" / "run-1" / "events.jsonl"
    lines = [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["sequence"] == 1
    assert lines[1]["sequence"] == 2


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


def test_redaction_preserves_safe_decoding_provenance_and_strips_sensitive_data() -> None:
    secret = "configured-secret-token"
    overlap_payload = {
        "status": "confirmed",
        "assessmentStatus": "valid",
        "summary": f"Overlap found with {secret}",
        "referenceSha256": "sha256:" + "a" * 64,
        "checkedFiles": [
            {
                "fileId": "file-1",
                "filename": "data.bin",
                "contentType": "application/octet-stream",
                "size": 128,
                "sha256": "b" * 64,
            }
        ],
        "matches": [
            {
                "referenceItemId": "ref-0001",
                "uploadedItemId": "item-0001",
                "matchType": "exact",
            }
        ],
        "decoding": {
            "status": "succeeded",
            "attemptCount": 1,
            "failureCode": None,
            "programSha256": ["c" * 64],
            "limitFlags": {"timedOut": False, "outputLimited": False},
            "derivedFiles": [
                {
                    "sourceFileId": "file-1",
                    "uploadedItemId": "item-0001",
                    "sha256": "d" * 64,
                    "size": 64,
                    "detectedContentType": "text/plain",
                }
            ],
            # Sensitive / ephemeral fields that should never survive or be retained
            "generatedSource": "print('secret code')",
            "decodedContent": "secret content bytes",
            "stdout": "secret output",
            "stderr": "error: secret info",
            "exception": "SecretException: failed",
            "sandboxId": "sbx-12345",
            "containerName": "docker-gamr-sbx",
            "hostPath": "/tmp/host/secret/path",
            "apiKey": secret,
        },
    }

    redacted = redact_payload({"contentOverlap": overlap_payload}, secrets=[secret])
    overlap = redacted["contentOverlap"]

    # Safe provenance is preserved
    assert overlap["status"] == "confirmed"
    assert overlap["summary"] == "Overlap found with [REDACTED]"
    assert "decoding" in overlap
    decoding = overlap["decoding"]
    assert decoding["status"] == "succeeded"
    assert decoding["attemptCount"] == 1
    assert decoding["failureCode"] is None
    assert decoding["programSha256"] == ["c" * 64]
    assert decoding["limitFlags"] == {"timedOut": False, "outputLimited": False}
    assert len(decoding["derivedFiles"]) == 1
    assert decoding["derivedFiles"][0]["sourceFileId"] == "file-1"
    assert decoding["derivedFiles"][0]["uploadedItemId"] == "item-0001"
    assert decoding["derivedFiles"][0]["sha256"] == "d" * 64
    assert decoding["derivedFiles"][0]["size"] == 64
    assert decoding["derivedFiles"][0]["detectedContentType"] == "text/plain"

    # Ephemeral / sensitive keys must be excluded
    for forbidden in (
        "generatedSource",
        "decodedContent",
        "stdout",
        "stderr",
        "exception",
        "sandboxId",
        "containerName",
        "hostPath",
        "apiKey",
    ):
        assert forbidden not in decoding

    # Validates into core model
    validated = ContentOverlapResult.model_validate(overlap)
    assert validated.decoding is not None
    assert validated.decoding.status.value == "succeeded"
    assert validated.decoding.attempt_count == 1
    assert len(validated.decoding.derived_files) == 1


def test_redaction_handles_decoding_safe_failure_and_limit_flags() -> None:
    secret = "super-secret-key"
    overlap_payload = {
        "status": "inconclusive",
        "assessmentStatus": "failed",
        "summary": f"Failed with {secret}",
        "checkedFiles": [
            {
                "fileId": "file-1",
                "filename": "archive.tar",
                "contentType": "application/x-tar",
                "size": 500,
                "sha256": "e" * 64,
            }
        ],
        "matches": [],
        "decoding": {
            "status": "failed",
            "attemptCount": 2,
            "failureCode": "timeout",
            "programSha256": ["1" * 64, "2" * 64],
            "limitFlags": {"timedOut": True, "outputLimited": False},
            "derivedFiles": [],
            "stdout": secret,
            "exception": f"TimeoutError: {secret}",
        },
    }

    redacted = redact_payload({"contentOverlap": overlap_payload}, secrets=[secret])
    decoding = redacted["contentOverlap"]["decoding"]
    assert decoding["status"] == "failed"
    assert decoding["attemptCount"] == 2
    assert decoding["failureCode"] == "timeout"
    assert decoding["limitFlags"] == {"timedOut": True, "outputLimited": False}
    assert decoding["programSha256"] == ["1" * 64, "2" * 64]
    assert decoding["derivedFiles"] == []
    assert "stdout" not in decoding
    assert "exception" not in decoding

    validated = ContentOverlapResult.model_validate(redacted["contentOverlap"])
    assert validated.decoding is not None
    assert validated.decoding.failure_code is not None
    assert validated.decoding.failure_code.value == "timeout"
    assert validated.decoding.limit_flags.timed_out is True


def test_redaction_preserves_reviewer_attempt_details_and_suppresses_unsafe_streams() -> None:
    source = (
        "from pathlib import Path\nprint('configured-secret')\nPath('/tmp/host.txt').read_text()"
    )
    payload = {
        "status": "succeeded",
        "action": "execute",
        "rationale": "The upload uses a reversible wrapper.",
        "attemptCount": 1,
        "programSha256": ["a" * 64],
        "limitFlags": {"timedOut": False, "outputLimited": False},
        "derivedFiles": [],
        "attempts": [
            {
                "attempt": 1,
                "stage": "output_validation",
                "source": source,
                "programSha256": "a" * 64,
                "execution": {
                    "exitCode": 0,
                    "elapsedSeconds": 0.4,
                    "timedOut": False,
                    "outputLimited": False,
                    "stdout": {"state": "captured", "value": "decoded [configured-secret]"},
                    "stderr": {
                        "state": "captured",
                        "value": "Traceback at /tmp/host.txt",
                    },
                },
                "derivedFiles": [],
            }
        ],
    }

    redacted = redact_payload(
        {
            "contentOverlap": {
                "status": "not_found",
                "assessmentStatus": "valid",
                "matches": [],
                "decoding": payload,
            }
        },
        secrets=["configured-secret"],
    )
    decoding = redacted["contentOverlap"]["decoding"]
    attempt = decoding["attempts"][0]

    assert decoding["action"] == "execute"
    assert decoding["rationale"] == "The upload uses a reversible wrapper."
    assert "configured-secret" not in attempt["source"]
    assert "/tmp/host.txt" not in attempt["source"]
    assert attempt["execution"]["stdout"] == {"state": "captured", "value": "decoded [[REDACTED]]"}
    assert attempt["execution"]["stderr"] == {"state": "suppressed"}

    validated = ContentOverlapResult.model_validate(redacted["contentOverlap"])
    assert validated.decoding is not None
    assert validated.decoding.attempts[0].program_sha256 == "a" * 64
