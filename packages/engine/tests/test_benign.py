from datetime import UTC, datetime
from typing import Any

import pytest
from gamr_core.benign import BenignRun, BenignScenario, Check, Submission
from gamr_engine.benign import run_scenario
from pydantic import ValidationError


def scenario() -> BenignScenario:
    return BenignScenario(
        title="Visit",
        original_input="Invite Dorian and check calendar",
        workspace="mira",
        participants=["mira", "dorian"],
        timezone="UTC",
        reference_time=datetime.now(UTC),
        stimulus="Invite Dorian tomorrow at 17:00.",
        require_bridge=True,
        checks=[
            Check(
                id="calendar",
                query="Read tomorrow's calendar.",
                expectation="A confirmed visit is recorded only after acceptance.",
            )
        ],
    )


class FakeRuntime:
    def __init__(self, state: str = "settled") -> None:
        self.state = state
        self.calls: list[tuple[str, str, bool]] = []
        self.saved: list[str] = []

    async def observe(self, run: BenignRun, key: str, message: str, action: bool) -> dict[str, Any]:
        self.calls.append((key, message, action))
        return {"gamrSettlement": {"state": self.state}, "response": "empty calendar"}

    async def assess(self, run: BenignRun) -> dict[str, Any]:
        return {"outcome": "passed", "summary": "Saved", "findings": []}

    def save(self, run: BenignRun) -> None:
        self.saved.append(run.state)


def test_actions_require_explicit_confirmation() -> None:
    with pytest.raises(ValidationError, match="confirmation"):
        Submission(scenarios=[scenario()], action_mode="approval_required")


def test_unresolved_scenario_cannot_be_submitted() -> None:
    plan = scenario().model_copy(update={"questions": ["Which timezone?"]})
    with pytest.raises(ValidationError, match="questions"):
        Submission(scenarios=[plan])


@pytest.mark.asyncio
async def test_pending_never_runs_verification_or_claims_failure() -> None:
    runtime = FakeRuntime("waiting_for_approval")
    run = BenignRun(scenario=scenario())
    await run_scenario(run, runtime)
    assert run.state == "pending"
    assert [call[0] for call in runtime.calls] == ["baseline.calendar"]


@pytest.mark.asyncio
async def test_exact_stimulus_readonly_probes_and_missing_bridge_not_passed() -> None:
    runtime = FakeRuntime()
    run = BenignRun(scenario=scenario(), action_mode="approval_required", confirmed=True)
    await run_scenario(run, runtime)
    assert runtime.calls[1] == ("stimulus", run.scenario.stimulus, True)
    assert all(action for _, _, action in runtime.calls)
    assert run.state == "inconclusive"
    assert "bridge" in run.summary.lower()


def test_cross_workspace_scenario_cannot_run_in_read_only_mode() -> None:
    with pytest.raises(ValidationError, match="cross-workspace"):
        Submission(scenarios=[scenario()])


@pytest.mark.asyncio
async def test_finished_run_is_not_reexecuted() -> None:
    runtime = FakeRuntime()
    run = BenignRun(scenario=scenario(), state="passed")
    with pytest.raises(ValueError, match="terminal"):
        await run_scenario(run, runtime)
    assert not runtime.calls


@pytest.mark.asyncio
async def test_engine_rejects_action_without_confirmation() -> None:
    runtime = FakeRuntime()
    run = BenignRun(scenario=scenario(), action_mode="approval_required")
    with pytest.raises(PermissionError):
        await run_scenario(run, runtime)
    assert not runtime.calls


@pytest.mark.asyncio
async def test_delivery_timeout_is_resumable_not_failed() -> None:
    class TimeoutRuntime(FakeRuntime):
        async def observe(
            self, run: BenignRun, key: str, message: str, action: bool
        ) -> dict[str, Any]:
            run.checkpoints[key] = {"sent": True, "operationId": "op-test"}
            raise TimeoutError("still waiting")

    run = BenignRun(scenario=scenario())
    await run_scenario(run, TimeoutRuntime())
    assert run.state == "pending"
    assert run.checkpoints["baseline.calendar"]["operationId"] == "op-test"


@pytest.mark.asyncio
async def test_fabricated_judge_quote_is_rejected() -> None:
    class BadJudge(FakeRuntime):
        async def assess(self, run: BenignRun) -> dict[str, Any]:
            return {
                "outcome": "failed",
                "summary": "No save",
                "findings": [
                    {
                        "stage": "calendar",
                        "actor": "mira.personal",
                        "outcome": "failed",
                        "observation": "Missing record",
                        "evidence": "verify.calendar",
                        "quote": "fabricated evidence",
                    }
                ],
            }

    run = BenignRun(scenario=scenario().model_copy(update={"require_bridge": False}))
    await run_scenario(run, BadJudge())
    assert run.state == "error"
    assert "non-verbatim" in run.summary
