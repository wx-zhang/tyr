import json
from typing import cast

import httpx
import pytest
from gamr_adapters.tyr.client import TyrMcpClient, TyrMcpError


@pytest.mark.asyncio
async def test_mcp_initialize_tools_and_tool_result_use_json_rpc_session() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if payload["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"serverInfo": {"name": "Tyr"}},
                },
            )
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        if payload["method"] == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"tools": [{"name": "tyr_assistant_query"}]},
                },
            )
        if payload["method"] == "tools/call":
            body = json.dumps({"operationId": "op-1", "state": "completed", "response": "ok"})
            event = {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": body}]},
            }
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                text=f"event: message\ndata: {json.dumps(event)}\n\n",
            )
        raise AssertionError(payload)

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        info = await client.initialize()
        tools = await client.list_tools()
        result = await client.call_tool("tyr_assistant_query", {"message": "status"})
    finally:
        await client.aclose()

    assert info["serverInfo"] == {"name": "Tyr"}
    assert tools == [{"name": "tyr_assistant_query"}]
    assert result["response"] == "ok"
    assert calls[1]["method"] == "notifications/initialized"
    assert calls[2]["method"] == "tools/list"
    assert calls[2]["params"] == {}


@pytest.mark.asyncio
async def test_mcp_errors_are_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {"code": -32000, "message": "denied"},
            },
        )

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(TyrMcpError, match="denied"):
            await client.list_tools()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_timeout_error_includes_type_and_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("")

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(TyrMcpError, match=r"tools/call.*ReadTimeout after 300s") as raised:
            await client.call_tool("tyr_assistant_query", {"message": "hi"})
    finally:
        await client.aclose()

    assert str(raised.value).rstrip(": ").endswith("ReadTimeout after 300s")
    assert not str(raised.value).endswith(": ")


@pytest.mark.asyncio
async def test_http_status_error_keeps_status_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(TyrMcpError, match=r"tools/list.*503") as raised:
            await client.list_tools()
    finally:
        await client.aclose()

    assert "HTTPStatusError" in str(raised.value) or "503" in str(raised.value)


@pytest.mark.asyncio
async def test_request_adds_idempotency_key_and_operation_id() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.update(payload)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": "{}"}]},
            },
        )

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        await client.request("do it", operation_id="op-1", idempotency_key="key-1")
    finally:
        await client.aclose()

    params = cast(dict[str, object], captured["params"])
    arguments = cast(dict[str, object], params["arguments"])
    assert params["name"] == "tyr_assistant_request"
    assert arguments == {"message": "do it", "operationId": "op-1", "idempotencyKey": "key-1"}


@pytest.mark.asyncio
async def test_start_conversation_and_query_pass_conversation_id() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        params = cast(dict[str, object], payload["params"])
        name = params["name"]
        body = (
            {"conversationId": "conversation-1"}
            if name == "tyr_assistant_start_conversation"
            else {"state": "completed", "response": "ok"}
        )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": json.dumps(body)}]},
            },
        )

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        start = await client.start_conversation(idempotency_key="start-key")
        result = await client.query(
            "continue",
            conversation_id=start["conversationId"],
            idempotency_key="key-1",
        )
    finally:
        await client.aclose()

    assert result["response"] == "ok"
    first_params = cast(dict[str, object], calls[0]["params"])
    second_params = cast(dict[str, object], calls[1]["params"])
    assert first_params == {
        "name": "tyr_assistant_start_conversation",
        "arguments": {"idempotencyKey": "start-key"},
    }
    assert second_params == {
        "name": "tyr_assistant_query",
        "arguments": {
            "message": "continue",
            "conversationId": "conversation-1",
            "idempotencyKey": "key-1",
        },
    }


@pytest.mark.asyncio
async def test_settle_falls_back_to_prior_operation_id_when_reply_omits_it() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["method"] == "tools/call"
        arguments = cast(dict[str, object], payload["params"]["arguments"])
        assert arguments["operationId"] == "op-prev"
        body = json.dumps({"operationId": "op-prev", "state": "completed", "response": "settled"})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": body}]},
            },
        )

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        # A bridge-routed reply that doesn't echo an operationId of its own --
        # settle() must fall back to the in-flight operation instead of
        # treating the reply as already settled.
        reply: dict[str, object] = {
            "state": "unknown",
            "response": "sent this across the bridge",
        }
        settled = await client.settle(reply, operation_id="op-prev")
    finally:
        await client.aclose()

    assert settled["gamrSettlement"] == {"state": "settled", "notes": []}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_settle_returns_reply_unchanged_without_any_operation_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("settle() must not call Tyr without an operation id")

    client = TyrMcpClient(
        "https://tyr.invalid/mcp",
        "secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        reply: dict[str, object] = {"state": "unknown", "response": "no operation yet"}
        settled = await client.settle(reply)
    finally:
        await client.aclose()

    assert settled == reply


@pytest.mark.live_tyr
@pytest.mark.asyncio
async def test_live_tyr_concurrent_operations_in_single_mcp_session() -> None:
    import asyncio
    import os

    from gamr_adapters.config import Settings

    settings = Settings()
    tyr_url = os.environ.get("TYR_MCP_URL") or settings.tyr_mcp_url
    tyr_token = os.environ.get("TYR_MCP_TOKEN") or settings.tyr_mcp_token

    if not tyr_token:
        pytest.skip("TYR_MCP_TOKEN not configured for live Tyr test")

    client = TyrMcpClient(tyr_url, tyr_token)
    try:
        init_result = await client.initialize()
        assert init_result is not None

        # Execute read-only queries concurrently in one MCP session
        results = await asyncio.gather(
            client.query("What tools are available?"),
            client.query("List current workspace files."),
            client.query("Show security policies."),
        )

        assert len(results) == 3
        for result in results:
            assert isinstance(result, dict)
            assert "error" not in result or result.get("error") is None
    finally:
        await client.aclose()
