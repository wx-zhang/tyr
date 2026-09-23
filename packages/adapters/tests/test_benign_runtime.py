from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from gamr_adapters.benign_config import BenignSettings, WorkspaceBinding
from gamr_adapters.benign_store import BenignStore
from gamr_adapters.benign_tyr import LiveBenignRuntime, RecordedTyr, fresh_history
from gamr_adapters.tyr.client import TyrMcpError
from gamr_core.benign import BenignRun, BenignScenario


@pytest.mark.parametrize(
    "history",
    [
        {},
        {"messages": []},
        {"messages": [{"createdAt": "bad"}]},
        {"messages": [{"createdAt": "2020-01-01T00:00:00Z"}]},
        {"hasMore": True, "messages": [{"createdAt": "2026-09-21T01:00:00Z"}]},
    ],
)
def test_stale_or_unknown_bridge_history_fails_closed(history: dict[str, Any]) -> None:
    assert not fresh_history(history, "2026-09-21T00:00:00Z")


def test_new_bridge_history() -> None:
    assert fresh_history(
        {"messages": [{"createdAt": "2026-09-21T01:00:00Z"}]}, "2026-09-21T00:00:00Z"
    )


def test_credentials_resolve_only_server_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = WorkspaceBinding(
        workspace_id="mira", url="https://example.test/mcp", token_env="BENIGN_TEST_TOKEN"
    )
    monkeypatch.delenv("BENIGN_TEST_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Missing server-side credential"):
        BenignSettings().token(binding)
    monkeypatch.setenv("BENIGN_TEST_TOKEN", "test-placeholder")
    assert BenignSettings().token(binding) == "test-placeholder"


@pytest.mark.asyncio
async def test_runtime_refuses_unapproved_action_before_network(tmp_path: Path) -> None:
    runtime = LiveBenignRuntime(BenignStore(tmp_path), BenignSettings())
    run = BenignRun(
        scenario=BenignScenario(
            title="Hello",
            original_input="Hello",
            workspace="mira",
            participants=["mira"],
            timezone="UTC",
            reference_time=datetime.now(UTC),
            stimulus="Hello",
        )
    )
    with pytest.raises(PermissionError):
        await runtime.observe(run, "stimulus", "Hello", True)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_credentials_are_logged_without_retry(tmp_path: Path, status: int) -> None:
    store = BenignStore(tmp_path)
    client = RecordedTyr("https://example.test/mcp", "test-placeholder", store, "run")
    await client.aclose()
    requests = []

    def reject(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"error": "unauthorized"})

    client._http = httpx.AsyncClient(transport=httpx.MockTransport(reject))
    async with client:
        with pytest.raises(TyrMcpError, match="HTTP"):
            await client.initialize()
    assert len(requests) == 1
    assert len(list((tmp_path / "run" / "evidence").glob("*.json"))) == 2
