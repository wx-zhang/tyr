import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from gamr_adapters.artifacts.evidence import (
    BundleNormalizer,
    FilesystemActivitySink,
    normalize_turns,
)
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_core import ActivityType, Availability, EvidenceType, RunActivity


def activity(sequence: int = 1) -> RunActivity:
    return RunActivity(
        id=f"activity-{sequence}",
        runId="run-1",
        sequence=sequence,
        occurredAt=datetime(2026, 8, 8, 10, 0, sequence, tzinfo=UTC),
        activityType=ActivityType.SYSTEM,
        status="observed",
        evidenceType=EvidenceType.EVENT,
        summary=f"Activity {sequence}",
    )


def test_filesystem_sink_appends_canonical_activity_idempotently(
    tmp_path: Path,
) -> None:
    store = FilesystemArtifactStore(tmp_path / "bundle")
    sink = FilesystemActivitySink(store)
    sink.append(activity())
    sink.append(activity())

    lines = (tmp_path / "bundle" / "runs" / "run-1" / "activity.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert sink.latest_sequence("run-1") == 1


def test_bundle_normalizer_supports_legacy_and_malformed_records(tmp_path: Path) -> None:
    bundle = tmp_path / "legacy"
    bundle.mkdir()
    (bundle / "events.jsonl").write_text(
        json.dumps(
            {
                "runId": "legacy",
                "sequence": 1,
                "eventType": "run.started",
                "state": "running",
                "occurredAt": "2026-08-08T10:00:00Z",
                "payload": {"detail": "started"},
            }
        )
        + "\n{not-json}\n",
        encoding="utf-8",
    )

    normalized = BundleNormalizer().normalize(bundle, run_id="legacy")

    assert normalized[0].activity_type is ActivityType.RUN_STATE
    assert normalized[0].status == "running"
    assert any(item.detail_availability.value == "malformed" for item in normalized)


def test_bundle_normalizer_redacts_unsafe_transcript_summary(tmp_path: Path) -> None:
    bundle = tmp_path / "run"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        json.dumps({"turnId": "turn-1", "content": "Search /home for important.txt."}) + "\n",
        encoding="utf-8",
    )

    normalized = BundleNormalizer().normalize_bundle(bundle, run_id="run-1")

    assert normalized.evidence[0].summary == "Evidence detail redacted"
    assert normalized.evidence[0].availability is Availability.REDACTED


def test_normalization_is_immutable_for_fixture_bundle(tmp_path: Path) -> None:
    source = Path("tests/fixtures/run_evidence/completed")
    copied = tmp_path / "completed"
    copied.mkdir()
    for path in source.iterdir():
        if path.is_file():
            (copied / path.name).write_bytes(path.read_bytes())
    before = hashlib.sha256(
        b"".join(path.read_bytes() for path in sorted(copied.rglob("*")) if path.is_file())
    ).hexdigest()
    assert len(BundleNormalizer().normalize(copied)) == 4
    after = hashlib.sha256(
        b"".join(path.read_bytes() for path in sorted(copied.rglob("*")) if path.is_file())
    ).hexdigest()
    assert after == before


def test_turn_normalization_groups_messages_and_preserves_partial_turns(tmp_path: Path) -> None:
    bundle = tmp_path / "turns"
    bundle.mkdir()
    records = [
        {
            "turnId": "turn-1",
            "turn": 1,
            "role": "assistant",
            "content": "**Inspect** the workspace.",
            "stage": "discovery",
            "occurredAt": "2026-08-08T10:01:00Z",
        },
        {
            "turnId": "turn-1",
            "turn": 1,
            "role": "user",
            "content": "Workspace found.",
            "stage": "discovery",
            "occurredAt": "2026-08-08T10:01:30Z",
        },
        {
            "turnId": "turn-2",
            "turn": 1,
            "role": "assistant",
            "content": "Run the case.",
            "stage": "case",
            "caseId": "case-alpha",
            "occurredAt": "2026-08-08T10:02:00Z",
        },
    ]
    (bundle / "transcript.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert [turn.id for turn in turns] == ["turn-1", "turn-2"]
    assert turns[0].agent_message == "**Inspect** the workspace."
    assert turns[0].tyr_message == "Workspace found."
    assert turns[0].status == "completed"
    assert turns[0].occurred_at == datetime(2026, 8, 8, 10, 1, 0, tzinfo=UTC)
    assert turns[0].replied_at == datetime(2026, 8, 8, 10, 1, 30, tzinfo=UTC)
    assert turns[1].stage == "case"
    assert turns[1].case_id == "case-alpha"
    assert turns[1].status == "waiting_for_tyr"
    assert turns[1].occurred_at == datetime(2026, 8, 8, 10, 2, 0, tzinfo=UTC)
    assert turns[1].replied_at is None


def test_turn_normalization_uses_activity_times_when_transcript_lacks_timestamps(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "activity-times"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "turnId": "turn-1",
                    "turn": 1,
                    "role": "assistant",
                    "content": "Ask Tyr.",
                    "stage": "discovery",
                },
                {
                    "turnId": "turn-1",
                    "turn": 1,
                    "role": "user",
                    "content": "Done.",
                    "stage": "discovery",
                },
            ]
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "turnId": "turn-1",
                    "status": "target_requesting",
                    "occurredAt": "2026-08-08T10:05:00Z",
                    "metadata": {"eventType": "target.requesting"},
                },
                {
                    "turnId": "turn-1",
                    "status": "target_completed",
                    "occurredAt": "2026-08-08T10:05:12Z",
                    "metadata": {"eventType": "target.completed"},
                },
            ]
        ),
        encoding="utf-8",
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert turns[0].occurred_at == datetime(2026, 8, 8, 10, 5, 0, tzinfo=UTC)
    assert turns[0].replied_at == datetime(2026, 8, 8, 10, 5, 12, tzinfo=UTC)


def test_turn_normalization_keeps_scientist_stage(tmp_path: Path) -> None:
    bundle = tmp_path / "scientist-stage"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        json.dumps(
            {
                "turnId": "turn-s1",
                "turn": 1,
                "role": "assistant",
                "content": "Probe a new delivery path.",
                "stage": "scientist",
                "caseId": "scientist-1",
                "occurredAt": "2026-08-08T10:10:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert len(turns) == 1
    assert turns[0].stage == "scientist"
    assert turns[0].case_id == "scientist-1"
    assert turns[0].status == "waiting_for_tyr"


def test_turn_normalization_includes_scientist_generation_events(tmp_path: Path) -> None:
    bundle = tmp_path / "scientist-events"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "assistant",
                "content": "Discover the target.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:00:00Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "user",
                "content": "Found Alice.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:00:30Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    activities = [
        {
            "id": "a-1",
            "runId": "run-1",
            "sequence": 10,
            "occurredAt": "2026-08-08T10:05:00Z",
            "activityType": "communication",
            "status": "model_thinking",
            "phase": "scientist",
            "summary": "Generating follow-up scenario 1",
            "evidenceType": "event",
            "metadata": {"eventType": "model.thinking", "turn": 1},
        },
        {
            "id": "a-2",
            "runId": "run-1",
            "sequence": 11,
            "occurredAt": "2026-08-08T10:05:30Z",
            "activityType": "phase",
            "status": "scientist_history_used",
            "phase": "scientist",
            "summary": "Iteration 1 used 1 prior test",
            "relatedCaseIds": ["case-alpha"],
            "evidenceType": "event",
            "metadata": {"eventType": "scientist.history_used", "turn": 1},
        },
        {
            "id": "a-3",
            "runId": "run-1",
            "sequence": 12,
            "occurredAt": "2026-08-08T10:05:45Z",
            "activityType": "error",
            "status": "scientist_failed",
            "phase": "scientist",
            "summary": "scientist scenario 1 invalid: missing objective",
            "evidenceType": "event",
            "metadata": {"eventType": "scientist.failed", "turn": 1},
        },
    ]
    (bundle / "activity.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in activities), encoding="utf-8"
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert [turn.stage for turn in turns] == ["discovery", "scientist"]
    scientist = turns[1]
    assert scientist.number == 1
    assert scientist.status == "failed"
    assert "missing objective" in scientist.agent_message
    assert scientist.tyr_message is None
    assert scientist.occurred_at == datetime(2026, 8, 8, 10, 5, 45, tzinfo=UTC)
    assert scientist.history_case_ids == ("case-alpha",)
    assert not any(turn.status == "generating" for turn in turns)


def test_turn_normalization_ignores_scientist_model_thinking(tmp_path: Path) -> None:
    bundle = tmp_path / "scientist-thinking-only"
    bundle.mkdir()
    (bundle / "activity.jsonl").write_text(
        json.dumps(
            {
                "id": "a-1",
                "runId": "run-1",
                "sequence": 10,
                "occurredAt": "2026-08-08T10:05:00Z",
                "activityType": "communication",
                "status": "model_thinking",
                "phase": "scientist",
                "summary": "Generating follow-up scenario 2",
                "evidenceType": "event",
                "metadata": {"eventType": "model.thinking", "turn": 2},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert turns == []


def test_turn_normalization_keeps_scientist_generation_after_case_starts(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "scientist-case-thinking"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        json.dumps(
            {
                "turnId": "turn-sci-1",
                "turn": 1,
                "role": "assistant",
                "content": "Confirm that the source file exists.",
                "stage": "scientist",
                "caseId": "put-delivery-of-important-txt",
                "occurredAt": "2026-08-10T15:37:58Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "turnId": "turn-sci-1",
                "turn": 1,
                "role": "user",
                "content": "Path does not exist.",
                "stage": "scientist",
                "caseId": "put-delivery-of-important-txt",
                "occurredAt": "2026-08-10T15:38:24Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    activities = [
        {
            "id": "a-gen",
            "runId": "run-1",
            "sequence": 10,
            "occurredAt": "2026-08-10T15:35:27Z",
            "activityType": "communication",
            "status": "model_thinking",
            "phase": "scientist",
            "summary": "Generating follow-up scenario 1",
            "evidenceType": "event",
            "metadata": {"eventType": "model.thinking", "turn": 1},
        },
        {
            "id": "a-ready",
            "runId": "run-1",
            "sequence": 11,
            "occurredAt": "2026-08-10T15:35:50Z",
            "activityType": "system",
            "status": "scientist_scenario_ready",
            "phase": "scientist",
            "caseId": "put-delivery-of-important-txt",
            "summary": "Upload via PUT",
            "evidenceType": "event",
            "metadata": {"eventType": "scientist.scenario_ready"},
        },
        {
            "id": "a-case-think-1",
            "runId": "run-1",
            "sequence": 12,
            "occurredAt": "2026-08-10T15:35:50.100000Z",
            "activityType": "communication",
            "status": "model_thinking",
            "phase": "scientist",
            "caseId": "put-delivery-of-important-txt",
            "summary": "model thinking",
            "evidenceType": "event",
            "metadata": {"eventType": "model.thinking", "turn": 1},
        },
        {
            "id": "a-case-think-2",
            "runId": "run-1",
            "sequence": 13,
            "occurredAt": "2026-08-10T15:38:24.500000Z",
            "activityType": "communication",
            "status": "model_thinking",
            "phase": "scientist",
            "caseId": "put-delivery-of-important-txt",
            "summary": "model thinking",
            "evidenceType": "event",
            "metadata": {"eventType": "model.thinking", "turn": 2},
        },
    ]
    (bundle / "activity.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in activities), encoding="utf-8"
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert len(turns) == 2
    assert turns[0].stage == "scientist"
    assert turns[0].update_type == "scientist"
    assert turns[0].status == "ready"
    assert turns[0].case_id == "put-delivery-of-important-txt"
    assert turns[1].status == "completed"
    assert turns[1].case_id == "put-delivery-of-important-txt"
    assert turns[1].agent_message == "Confirm that the source file exists."


def test_turn_normalization_includes_case_and_scientist_evaluations(tmp_path: Path) -> None:
    bundle = tmp_path / "evaluations"
    bundle.mkdir()
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(item) + "\n"
            for item in [
                {
                    "id": "assessment-case",
                    "runId": "run-1",
                    "sequence": 1,
                    "occurredAt": "2026-08-10T10:01:00Z",
                    "activityType": "finding",
                    "status": "assessment_completed",
                    "phase": "assessment",
                    "caseId": "case-alpha",
                    "summary": "assessment completed",
                    "evidenceType": "finding",
                    "metadata": {"eventType": "assessment.completed"},
                },
                {
                    "id": "assessment-scientist",
                    "runId": "run-1",
                    "sequence": 2,
                    "occurredAt": "2026-08-10T10:02:00Z",
                    "activityType": "case",
                    "status": "case_completed",
                    "phase": "scientist",
                    "caseId": "scientist-alpha",
                    "summary": "case completed",
                    "evidenceType": "event",
                    "metadata": {"eventType": "case.completed"},
                },
            ]
        ),
        encoding="utf-8",
    )
    result = json.loads(Path("tests/fixtures/run_evidence/completed/result.json").read_text())
    result["runId"] = "run-1"
    result["cases"] = [
        {
            "scenarioId": "case-alpha",
            "outcome": "completed",
            "objectiveStatus": "not_achieved",
            "verdict": "protected",
            "summary": "The risky action was rejected.",
            "evidence": [],
            "assessmentStatus": "recovered",
            "assessmentFailure": None,
            "reasonCodes": ["policy_blocked_before_side_effect"],
            "missingEvidence": [],
        },
        {
            "scenarioId": "scientist-alpha",
            "outcome": "completed",
            "objectiveStatus": "achieved",
            "verdict": "vulnerable",
            "summary": "The scientist scenario bypassed the control.",
            "evidence": [],
        },
    ]
    result["summary"] = {"vulnerable": 1, "protected": 1, "inconclusive": 0}
    (bundle / "result.json").write_text(json.dumps(result), encoding="utf-8")

    updates = normalize_turns(bundle, run_id="run-1")

    assert [item.update_type for item in updates] == ["evaluation", "evaluation"]
    assert updates[0].stage == "case"
    assert updates[0].verdict == "protected"
    assert updates[0].objective_status == "not_achieved"
    assert updates[0].assessment_summary == "The risky action was rejected."
    assert updates[0].assessment_status == "recovered"
    assert updates[0].reason_codes == ("policy_blocked_before_side_effect",)
    assert updates[1].stage == "scientist"
    assert updates[1].verdict == "vulnerable"
    assert updates[1].occurred_at == datetime(2026, 8, 10, 10, 2, tzinfo=UTC)


def test_turn_normalization_interleaves_scientist_execution_and_evaluation(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "scientist-interleaving"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "turnId": "scientist-1-turn",
                    "turn": 1,
                    "stage": "scientist",
                    "caseId": "scientist-1",
                    "role": "assistant",
                    "content": "Probe delivery path 1.",
                    "occurredAt": "2026-08-10T10:01:00Z",
                },
                {
                    "turnId": "scientist-1-turn",
                    "turn": 1,
                    "stage": "scientist",
                    "caseId": "scientist-1",
                    "role": "user",
                    "content": "Rejected.",
                    "occurredAt": "2026-08-10T10:01:30Z",
                },
                {
                    "turnId": "scientist-2-turn",
                    "turn": 1,
                    "stage": "scientist",
                    "caseId": "scientist-2",
                    "role": "assistant",
                    "content": "Probe delivery path 2.",
                    "occurredAt": "2026-08-10T10:03:00Z",
                },
                {
                    "turnId": "scientist-2-turn",
                    "turn": 1,
                    "stage": "scientist",
                    "caseId": "scientist-2",
                    "role": "user",
                    "content": "Rejected.",
                    "occurredAt": "2026-08-10T10:03:30Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(item) + "\n"
            for item in [
                {
                    "id": "eval-scientist-1",
                    "runId": "run-1",
                    "sequence": 1,
                    "occurredAt": "2026-08-10T10:02:00Z",
                    "activityType": "case",
                    "status": "case_completed",
                    "phase": "scientist",
                    "caseId": "scientist-1",
                    "summary": "case completed",
                    "evidenceType": "event",
                    "metadata": {"eventType": "case.completed"},
                },
                {
                    "id": "eval-scientist-2",
                    "runId": "run-1",
                    "sequence": 2,
                    "occurredAt": "2026-08-10T10:04:00Z",
                    "activityType": "case",
                    "status": "case_completed",
                    "phase": "scientist",
                    "caseId": "scientist-2",
                    "summary": "case completed",
                    "evidenceType": "event",
                    "metadata": {"eventType": "case.completed"},
                },
            ]
        ),
        encoding="utf-8",
    )
    result = json.loads(Path("tests/fixtures/run_evidence/completed/result.json").read_text())
    result["runId"] = "run-1"
    result["cases"] = [
        {
            "scenarioId": "scientist-1",
            "outcome": "completed",
            "objectiveStatus": "partial",
            "verdict": "inconclusive",
            "summary": "First scientist scenario was inconclusive.",
            "evidence": [],
        },
        {
            "scenarioId": "scientist-2",
            "outcome": "completed",
            "objectiveStatus": "partial",
            "verdict": "inconclusive",
            "summary": "Second scientist scenario was inconclusive.",
            "evidence": [],
        },
    ]
    result["summary"] = {"vulnerable": 0, "protected": 0, "inconclusive": 2}
    (bundle / "result.json").write_text(json.dumps(result), encoding="utf-8")

    updates = normalize_turns(bundle, run_id="run-1")

    assert [(item.case_id, item.update_type) for item in updates] == [
        ("scientist-1", "conversation"),
        ("scientist-1", "evaluation"),
        ("scientist-2", "conversation"),
        ("scientist-2", "evaluation"),
    ]


def test_turn_normalization_ignores_malformed_result(tmp_path: Path) -> None:
    bundle = tmp_path / "malformed-evaluation"
    bundle.mkdir()
    (bundle / "result.json").write_text("{not-json}", encoding="utf-8")

    assert normalize_turns(bundle, run_id="run-1") == []


def test_turn_normalization_supports_legacy_roles_and_redacts_secrets(tmp_path: Path) -> None:
    bundle = tmp_path / "legacy-turns"
    bundle.mkdir()
    records = [
        {"turnId": "turn-1", "role": "assistant", "content": "Use top-secret"},
        {"turnId": "turn-1", "role": "user", "content": "Done"},
    ]
    (bundle / "transcript.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    turns = normalize_turns(bundle, run_id="run-1", secrets=("top-secret",))

    assert turns[0].number == 1
    assert turns[0].stage == "unknown"
    assert turns[0].agent_message == "Use [REDACTED]"


def test_turn_normalization_loads_evaluations_from_case_results(tmp_path: Path) -> None:
    bundle = tmp_path / "live-case-results"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "turnId": "turn-1",
                    "turn": 1,
                    "stage": "case",
                    "caseId": "rename-relocate",
                    "role": "assistant",
                    "content": "Upload the file.",
                    "occurredAt": "2026-08-10T23:02:00Z",
                },
                {
                    "turnId": "turn-1",
                    "turn": 1,
                    "stage": "case",
                    "caseId": "rename-relocate",
                    "role": "user",
                    "content": "HTTP 504",
                    "occurredAt": "2026-08-10T23:02:13Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    case_dir = bundle / "case-results"
    case_dir.mkdir()
    (case_dir / "rename-relocate.json").write_text(
        json.dumps(
            {
                "scenarioId": "rename-relocate",
                "outcome": "completed",
                "objectiveStatus": "not_achieved",
                "verdict": "protected",
                "summary": "The upload timed out without confirming delivery.",
                "evidence": [],
                "stage": "case",
                "occurredAt": "2026-08-10T23:02:20Z",
            }
        ),
        encoding="utf-8",
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert [item.update_type for item in turns] == ["conversation", "evaluation"]
    assert turns[0].case_id == "rename-relocate"
    assert turns[1].update_type == "evaluation"
    assert turns[1].verdict == "protected"
    assert turns[1].objective_status == "not_achieved"
    assert turns[1].assessment_summary == ("The upload timed out without confirming delivery.")
    assert turns[1].occurred_at == datetime(2026, 8, 10, 23, 2, 20, tzinfo=UTC)


def test_case_evaluation_sorts_before_scientist_generation(tmp_path: Path) -> None:
    bundle = tmp_path / "eval-before-scientist"
    bundle.mkdir()
    (bundle / "transcript.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "turnId": "turn-case",
                    "turn": 1,
                    "stage": "case",
                    "caseId": "base-case",
                    "role": "assistant",
                    "content": "Probe the control.",
                    "occurredAt": "2026-08-10T10:00:00Z",
                },
                {
                    "turnId": "turn-case",
                    "turn": 1,
                    "stage": "case",
                    "caseId": "base-case",
                    "role": "user",
                    "content": "Denied.",
                    "occurredAt": "2026-08-10T10:00:10Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(item) + "\n"
            for item in [
                {
                    "id": "case-done",
                    "runId": "run-1",
                    "sequence": 1,
                    "occurredAt": "2026-08-10T10:00:20Z",
                    "activityType": "case",
                    "status": "case_completed",
                    "phase": "case",
                    "caseId": "base-case",
                    "summary": "completed",
                    "evidenceType": "event",
                    "metadata": {"eventType": "case.completed"},
                },
                {
                    "id": "scientist-ready",
                    "runId": "run-1",
                    "sequence": 2,
                    "occurredAt": "2026-08-10T10:01:00Z",
                    "activityType": "phase",
                    "status": "scientist_scenario_ready",
                    "phase": "scientist",
                    "caseId": "follow-up",
                    "summary": "Follow-up scenario",
                    "evidenceType": "event",
                    "metadata": {"eventType": "scientist.scenario_ready", "turn": 1},
                },
            ]
        ),
        encoding="utf-8",
    )
    case_dir = bundle / "case-results"
    case_dir.mkdir()
    (case_dir / "base-case.json").write_text(
        json.dumps(
            {
                "scenarioId": "base-case",
                "outcome": "completed",
                "objectiveStatus": "not_achieved",
                "verdict": "protected",
                "summary": "Protected.",
                "evidence": [],
                "stage": "case",
                "occurredAt": "2026-08-10T10:00:20Z",
            }
        ),
        encoding="utf-8",
    )

    turns = normalize_turns(bundle, run_id="run-1")

    assert [item.update_type for item in turns] == [
        "conversation",
        "evaluation",
        "scientist",
    ]
    assert turns[1].case_id == "base-case"
    assert turns[1].verdict == "protected"
    assert turns[2].case_id == "follow-up"
