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
            "activityType": "error",
            "status": "scientist_failed",
            "phase": "scientist",
            "summary": "scientist scenario 1 invalid: missing objective",
            "evidenceType": "event",
            "metadata": {"eventType": "scientist.failed"},
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
    assert scientist.occurred_at == datetime(2026, 8, 8, 10, 5, 30, tzinfo=UTC)


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
