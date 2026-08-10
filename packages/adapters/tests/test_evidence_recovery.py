from datetime import UTC, datetime
from pathlib import Path

import pytest
from gamr_adapters.artifacts.evidence import BundleNormalizer, FilesystemActivitySink
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_core import ActivityType, EvidenceType, RunActivity


def activity(sequence: int, *, summary: str | None = None) -> RunActivity:
    return RunActivity(
        id=f"activity-{sequence}",
        runId="run-recovery",
        sequence=sequence,
        occurredAt=datetime(2026, 8, 8, 10, 0, sequence, tzinfo=UTC),
        activityType=ActivityType.SYSTEM,
        status="observed",
        evidenceType=EvidenceType.EVENT,
        summary=summary or f"Activity {sequence}",
    )


def test_filesystem_sink_rejects_conflicting_duplicate_activity(tmp_path: Path) -> None:
    sink = FilesystemActivitySink(FilesystemArtifactStore(tmp_path))
    sink.append(activity(1))

    with pytest.raises(ValueError, match="different content"):
        sink.append(activity(1, summary="changed"))


def test_normalizer_orders_late_canonical_records_without_mutation(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    for item in (activity(3), activity(1), activity(2)):
        store.append_activity(item.model_dump(by_alias=True, mode="json"))
    path = tmp_path / "runs" / "run-recovery" / "activity.jsonl"
    before = path.read_bytes()

    normalized = BundleNormalizer().normalize(path.parent, run_id="run-recovery")

    assert [item.sequence for item in normalized] == [1, 2, 3]
    assert path.read_bytes() == before
