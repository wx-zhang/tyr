import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from gamr_adapters.tyr.client import TyrMcpClient


def operation(
    bridge_id: str,
    reply: str | None,
    *,
    operation_id: str = "operation-1",
    response: str = "Forwarded to the peer",
) -> dict[str, object]:
    return {
        "operationId": operation_id,
        "state": "completed",
        "response": response,
        "bridges": [
            {
                "bridgeRequestId": bridge_id,
                "state": "completed" if reply is not None else "delivered",
                "response": reply,
            }
        ],
    }


@asynccontextmanager
async def client_responses(responses: list[dict[str, object]]) -> AsyncIterator[TyrMcpClient]:
    remaining = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": json.dumps(next(remaining))}]},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        yield TyrMcpClient("https://tyr.invalid/mcp", "test-token", http_client=http)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["query", "request"])
async def test_unchanged_bridge_does_not_replace_fresh_top_level_response(action: str) -> None:
    old = operation("bridge-1", "The peer's previous answer")
    fresh = operation(
        "bridge-1", "The peer's previous answer", response="APPROVAL: <approval state unknown>"
    )
    async with client_responses([old, fresh]) as client:
        first = await client.query("first", operation_id="operation-1")
        settled_first = await client.settle(first)
        send = client.query if action == "query" else client.request
        second = await send("approval?", operation_id="operation-1")
        settled_second = await client.settle(second)

    assert settled_first["gamrSettlement"] == {
        "state": "settled",
        "notes": [],
        "reply": "The peer's previous answer",
    }
    assert second == fresh
    assert settled_second["response"] == "APPROVAL: <approval state unknown>"
    assert settled_second["bridges"] == fresh["bridges"]
    assert settled_second["gamrSettlement"] == {"state": "settled", "notes": []}


@pytest.mark.asyncio
async def test_new_bridge_can_repeat_the_previous_bridge_text() -> None:
    first = operation("bridge-1", "No approval available")
    second = operation("bridge-2", "No approval available")
    async with client_responses([first, second]) as client:
        await client.settle(await client.query("first", conversation_id="conversation-1"))
        result = await client.settle(
            await client.request(
                "again", conversation_id="conversation-1", operation_id="operation-1"
            )
        )

    assert result["gamrSettlement"] == {
        "state": "settled",
        "notes": [],
        "reply": "No approval available",
    }


@pytest.mark.asyncio
async def test_existing_bridge_changed_reply_is_fresh() -> None:
    first = operation("bridge-1", "Previous answer")
    changed = operation("bridge-1", "Updated answer")
    async with client_responses([first, changed]) as client:
        await client.settle(await client.query("first", operation_id="operation-1"))
        result = await client.settle(await client.query("again", operation_id="operation-1"))

    assert result["gamrSettlement"] == {"state": "settled", "notes": [], "reply": "Updated answer"}


@pytest.mark.asyncio
async def test_pending_bridge_completes_during_settlement_and_is_not_reused() -> None:
    pending = operation("bridge-1", None)
    completed = operation("bridge-1", "Late peer answer")
    fresh = operation("bridge-1", "Late peer answer", response="Fresh local answer")
    async with client_responses([pending, completed, fresh]) as client:
        result = await client.settle(await client.query("first", operation_id="operation-1"))
        next_result = await client.settle(await client.query("next", operation_id="operation-1"))

    assert result["gamrSettlement"] == {
        "state": "settled",
        "notes": [],
        "reply": "Late peer answer",
    }
    assert next_result["response"] == "Fresh local answer"
    assert next_result["gamrSettlement"] == {"state": "settled", "notes": []}


@pytest.mark.asyncio
async def test_immediate_observations_without_settle_still_establish_freshness() -> None:
    old = operation("bridge-1", "Previous answer")
    fresh = operation("bridge-1", "Previous answer", response="Fresh local answer")
    async with client_responses([old, fresh]) as client:
        await client.query("first", operation_id="operation-1")
        result = await client.settle(await client.request("next", operation_id="operation-1"))

    assert result["response"] == "Fresh local answer"
    assert result["gamrSettlement"] == {"state": "settled", "notes": []}


@pytest.mark.asyncio
async def test_interleaved_conversations_do_not_share_bridge_observations() -> None:
    first = operation("bridge-1", "Same peer answer")
    other = operation("bridge-1", "Same peer answer", operation_id="operation-2")
    fresh = operation("bridge-1", "Same peer answer", response="First conversation's fresh answer")
    async with client_responses([first, other, fresh]) as client:
        pending_first = await client.query("first", conversation_id="conversation-1")
        pending_other = await client.query("other", conversation_id="conversation-2")
        result_other = await client.settle(pending_other)
        result_first = await client.settle(pending_first)
        next_first = await client.settle(
            await client.query("next", operation_id="operation-1", conversation_id="conversation-1")
        )

    assert (
        result_first["gamrSettlement"]
        == result_other["gamrSettlement"]
        == {"state": "settled", "notes": [], "reply": "Same peer answer"}
    )
    assert next_first["response"] == "First conversation's fresh answer"
    assert next_first["gamrSettlement"] == {"state": "settled", "notes": []}
