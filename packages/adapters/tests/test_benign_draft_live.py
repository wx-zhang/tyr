import os
from pathlib import Path
from time import monotonic

import pytest
from gamr_adapters.benign_model import BenignModel
from gamr_adapters.benign_store import BenignStore


@pytest.mark.live_tyr
@pytest.mark.skipif(os.environ.get("BENIGN_LIVE_DRAFT_TEST") != "1", reason="Opt-in model call")
@pytest.mark.asyncio
async def test_live_draft_without_tyr_execution() -> None:
    store = BenignStore(Path(".gamr/benign"))
    started = monotonic()
    plan = await BenignModel(store).draft(
        "mira invite dorian to come tomorrow 5pm and then check mira's calendar",
        "mira",
        "Asia/Riyadh",
    )
    print(f"Draft saved: {plan.id}; elapsed: {monotonic() - started:.1f}s")
    assert plan.workspace == "mira"
    assert "dorian" in plan.participants
    assert plan.require_bridge
    assert plan.checks
    assert (store.directory(plan.id) / "scenario.json").exists()
    assert not (store.directory(plan.id) / "run.json").exists()
