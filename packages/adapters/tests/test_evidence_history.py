from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from gamr_adapters.artifacts.evidence import BundleNormalizer


@pytest.fixture
def run_evidence_bundle() -> Callable[[str], Path]:
    root = Path(__file__).parents[3] / "tests" / "fixtures" / "run_evidence"

    def resolve(name: str) -> Path:
        return root / name

    return resolve


def _bundle(tmp_path: Path, status: str, records: list[dict[str, object]]) -> Path:
    root = tmp_path / status
    root.mkdir()
    (root / "run.json").write_text(
        json.dumps({"runId": f"run-{status}", "status": status}), encoding="utf-8"
    )
    (root / "events.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return root


def test_completed_run_json_synthesizes_terminal_activity_when_missing(tmp_path: Path) -> None:
    root = tmp_path / "cli-complete"
    root.mkdir()
    (root / "run.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "id": "run-cli",
                "state": "completed",
                "finishedAt": "2026-08-08T10:05:00Z",
                "updatedAt": "2026-08-08T10:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    (root / "activity.jsonl").write_text(
        json.dumps(
            {
                "id": "activity-1",
                "runId": "run-cli",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:00Z",
                "activityType": "run_state",
                "status": "running",
                "evidenceType": "event",
                "summary": "Run started",
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "activity-2",
                "runId": "run-cli",
                "sequence": 2,
                "occurredAt": "2026-08-08T10:04:00Z",
                "activityType": "phase",
                "status": "discovery_completed",
                "phase": "discovery",
                "evidenceType": "event",
                "summary": "discovery completed",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    first = BundleNormalizer().normalize(root, run_id="run-cli")
    second = BundleNormalizer().normalize(root, run_id="run-cli")

    assert first[-1].activity_type.value == "run_state"
    assert first[-1].status == "completed"
    assert first[-1].sequence == 3
    assert [item.id for item in first] == [item.id for item in second]


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "interrupted"])
def test_terminal_bundle_states_are_normalized(tmp_path: Path, status: str) -> None:
    root = _bundle(
        tmp_path,
        status,
        [
            {
                "id": f"activity-{status}",
                "runId": f"run-{status}",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:00Z",
                "activityType": "run_state",
                "status": status,
                "evidenceType": "event",
                "summary": f"Run {status}",
            }
        ],
    )

    activities = BundleNormalizer().normalize(root)

    assert activities[0].run_id == f"run-{status}"
    assert activities[0].status == status


def test_legacy_records_are_ordered_deterministically(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        "legacy",
        [
            {
                "runId": "run-legacy",
                "sequence": 2,
                "occurredAt": "2026-08-08T10:00:02Z",
                "eventType": "case.completed",
                "payload": {"summary": "second"},
            },
            {
                "runId": "run-legacy",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:01Z",
                "eventType": "run.started",
                "payload": {"summary": "first"},
            },
        ],
    )

    first = BundleNormalizer().normalize(root)
    second = BundleNormalizer().normalize(root)

    assert [item.sequence for item in first] == [1, 2]
    assert [item.id for item in first] == [item.id for item in second]


def test_evidence_gaps_and_malformed_detail_are_explicit_and_immutable(
    run_evidence_bundle: Callable[[str], Path], tmp_path: Path
) -> None:
    source = run_evidence_bundle("completed")
    before = {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }

    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "run.json").write_text(
        json.dumps({"runId": "run-missing", "status": "completed"}), encoding="utf-8"
    )
    (missing / "result.json").write_text(
        json.dumps(
            {
                "runId": "run-missing",
                "outcome": "completed",
                "cases": [{"scenarioId": "case-a", "evidence": [{"artifact": "raw/nope.json"}]}],
            }
        ),
        encoding="utf-8",
    )

    normalized = BundleNormalizer().normalize_bundle(missing)
    malformed = BundleNormalizer().normalize_bundle(run_evidence_bundle("malformed"))

    assert any(item.availability.value == "missing" for item in normalized.evidence)
    assert any(item.availability.value == "malformed" for item in malformed.evidence)
    assert {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()
    } == before


def test_malformed_decoding_history_normalizes_safely(tmp_path: Path) -> None:
    bundle = tmp_path / "malformed-decoding"
    bundle.mkdir()
    (bundle / "run.json").write_text(
        json.dumps({"runId": "run-malformed", "status": "completed"}), encoding="utf-8"
    )
    # result.json with malformed decoding provenance
    # (e.g. bad program sha256 or mismatched attempts)
    (bundle / "result.json").write_text(
        json.dumps(
            {
                "runId": "run-malformed",
                "task": {"id": "demo", "version": "1.0", "digest": "sha256:0"},
                "startedAt": "2026-08-08T10:00:00Z",
                "outcome": "completed",
                "configuration": {"actionMode": "read_only"},
                "summary": {"vulnerable": 0, "protected": 0, "inconclusive": 1},
                "cases": [
                    {
                        "scenarioId": "case-bad",
                        "outcome": "completed",
                        "verdict": "inconclusive",
                        "summary": "inconclusive",
                        "evidence": [],
                        "assessmentStatus": "failed",
                        "contentOverlap": {
                            "status": "inconclusive",
                            "assessmentStatus": "failed",
                            "matches": [],
                            "decoding": {
                                "status": "succeeded",
                                "attemptCount": 5,  # Invalid: > 3
                                "programSha256": ["invalid-sha"],
                            },
                        },
                    }
                ],
                "findings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    normalized = BundleNormalizer().normalize_bundle(bundle)
    # Malformed result is handled safely without crashing
    assert normalized is not None
