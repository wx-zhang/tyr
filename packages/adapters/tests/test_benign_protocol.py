from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from gamr_adapters.benign_config import BenignSettings, WorkspaceBinding
from gamr_adapters.benign_store import BenignStore
from gamr_adapters.benign_tyr import LiveBenignRuntime
from gamr_adapters.tyr.client import TyrMcpError
from gamr_core.benign import BenignRun, BenignScenario


class FakeTyr:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.conversation: dict[str, Any] = {"conversationId": "fresh-conversation"}

    async def __aenter__(self) -> FakeTyr:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def initialize(self) -> None:
        pass

    async def start_conversation(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("start", kwargs))
        return self.conversation

    async def query(self, message: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("query", message))
        return {"operationId": "new-op", "state": "completed"}

    async def request(self, message: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("request", message))
        return {"operationId": "new-op", "state": "completed"}

    async def operation_status(self, operation_id: str) -> dict[str, Any]:
        self.calls.append(("status", operation_id))
        return {"state": "completed"}

    async def settle(self, result: Any, **kwargs: Any) -> dict[str, Any]:
        return {**result, "gamrSettlement": {"state": "settled"}}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[LiveBenignRuntime, FakeTyr]:
    client = FakeTyr()
    monkeypatch.setattr("gamr_adapters.benign_tyr.RecordedTyr", lambda *args: client)
    monkeypatch.setattr(
        BenignSettings,
        "bindings",
        lambda _: {
            "mira": WorkspaceBinding(
                workspace_id="mira", url="https://example.test/mcp", token_env="TEST_TOKEN"
            )
        },
    )
    monkeypatch.setattr(BenignSettings, "token", lambda *args: "test-placeholder")
    return LiveBenignRuntime(BenignStore(tmp_path), BenignSettings()), client


def run() -> BenignRun:
    return BenignRun(
        scenario=BenignScenario(
            title="Invite",
            original_input="Invite Dorian",
            workspace="mira",
            participants=["mira"],
            timezone="UTC",
            reference_time=datetime.now(UTC),
            stimulus="Invite Dorian",
        ),
        action_mode="approval_required",
        confirmed=True,
    )


@pytest.mark.asyncio
async def test_action_enabled_verification_uses_read_only_request(runtime: Any) -> None:
    adapter, client = runtime
    record = run()
    await adapter.observe(record, "stimulus", "Invite Dorian", True)
    assert ("request", "Invite Dorian") in client.calls
    client.conversation = {"conversationId": "verification-conversation"}
    await adapter.observe(record, "verify.calendar", "Read calendar", True)
    assert client.calls[-1][0] == "request"
    assert "Do not create" in client.calls[-1][1]


@pytest.mark.asyncio
async def test_conversation_title_respects_tyr_limit(runtime: Any) -> None:
    adapter, client = runtime
    record = run()
    key = "baseline." + "calendar-check-with-a-very-long-generated-identifier" * 2
    await adapter.observe(record, key, "Read calendar", False)
    start = next(value for name, value in client.calls if name == "start")
    assert len(start["title"]) <= 72


@pytest.mark.asyncio
async def test_resume_only_polls_original_operation(runtime: Any) -> None:
    adapter, client = runtime
    record = run()
    record.checkpoints["stimulus"] = {"conversationId": "old-conv", "operationId": "old-op"}
    await adapter.observe(record, "stimulus", "Invite Dorian", True)
    assert client.calls == [("status", "old-op")]


@pytest.mark.asyncio
async def test_unknown_delivery_never_replays(runtime: Any) -> None:
    adapter, client = runtime
    record = run()
    record.checkpoints["stimulus"] = {"conversationId": "old-conv", "sent": True}
    with pytest.raises(ValueError, match="Delivery uncertain"):
        await adapter.observe(record, "stimulus", "Invite Dorian", True)
    assert not client.calls


@pytest.mark.asyncio
async def test_missing_conversation_id_stops_before_sending(runtime: Any) -> None:
    adapter, client = runtime
    client.conversation = {}
    with pytest.raises(ValueError, match="conversation ID"):
        await adapter.observe(run(), "stimulus", "Invite Dorian", True)
    assert [name for name, _ in client.calls] == ["start"]


@pytest.mark.asyncio
async def test_reused_local_conversation_id_stops_before_sending(runtime: Any) -> None:
    adapter, client = runtime
    record = run()
    record.checkpoints["baseline.calendar"] = {"conversationId": "fresh-conversation"}
    adapter.save(record)
    with pytest.raises(ValueError, match="reused"):
        await adapter.observe(record, "stimulus", "Invite Dorian", True)
    assert [name for name, _ in client.calls] == ["start"]


@pytest.mark.asyncio
async def test_history_permission_failure_preserves_stimulus(
    runtime: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _ = runtime
    record = run()
    record.scenario.require_bridge = True

    async def denied(*args: Any) -> bool:
        raise TyrMcpError("Missing bridge read permission")

    monkeypatch.setattr(adapter, "_bridges", denied)
    result = await adapter.observe(record, "stimulus", "Invite Dorian", True)
    assert result["state"] == "completed"
    assert result["benignFreshBridgeVerified"] is False
    assert "permission" in result["benignBridgeVerificationError"]
