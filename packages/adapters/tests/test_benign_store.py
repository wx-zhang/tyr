from datetime import UTC, datetime
from pathlib import Path

import pytest
from gamr_adapters.benign_store import BenignStore
from gamr_core.benign import BenignRun, BenignScenario, Submission


def plan() -> BenignScenario:
    return BenignScenario(
        title="Hello",
        original_input="Hello",
        workspace="mira",
        participants=["mira"],
        timezone="UTC",
        reference_time=datetime(2026, 9, 21, tzinfo=UTC),
        stimulus="Hello",
    )


def test_batch_persists_and_shared_participants_lock(tmp_path: Path) -> None:
    store = BenignStore(tmp_path)
    runs = store.enqueue(Submission(scenarios=[plan()], repeat=2))
    assert len(runs) == 2
    assert len(BenignStore(tmp_path).list_runs()) == 2
    with store.claim(runs[0]) as first:
        assert first
        with store.claim(runs[1]) as second:
            assert not second


def test_paths_are_confined(tmp_path: Path) -> None:
    store = BenignStore(tmp_path)
    with pytest.raises(ValueError):
        store.read("../escape")


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = BenignStore(root)
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        store.read("escape")


def test_completed_result_cannot_be_overwritten(tmp_path: Path) -> None:
    store = BenignStore(tmp_path)
    run = BenignRun(scenario=plan(), state="passed")
    store.save(run)
    run.summary = "changed"
    with pytest.raises(ValueError, match="immutable"):
        store.save(run)
