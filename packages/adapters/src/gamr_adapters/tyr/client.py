from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import uuid4

import httpx

from .operations import BridgeSnapshot, bridge_snapshot, settle_operation

#: A single synchronous tools/call can span the local assistant's full
#: bridge relay to a peer (including the peer's own processing); 60s cut live runs off.
TOOL_CALL_TIMEOUT_SECONDS = 300.0


class TyrMcpError(RuntimeError):
    pass


class TyrMcpClient:
    def __init__(
        self,
        url: str,
        token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise TyrMcpError("Tyr MCP token is required")
        self.url = url
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._http = http_client or httpx.AsyncClient(timeout=TOOL_CALL_TIMEOUT_SECONDS)
        self._owns_http = http_client is None
        self._rpc_id = 0
        self._session_id: str | None = None
        self._bridge_observations: dict[tuple[str, str], BridgeSnapshot] = {}
        self._bridge_requests: dict[str, tuple[tuple[str, str], BridgeSnapshot]] = {}

    async def __aenter__(self) -> TyrMcpClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _post(
        self,
        method: str,
        params: Mapping[str, object] | None = None,
        *,
        timeout: float = TOOL_CALL_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        payload: dict[str, object] = {"jsonrpc": "2.0", "method": method}
        if not method.startswith("notifications/"):
            payload["id"] = self._next_id()
        if params is not None:
            payload["params"] = dict(params)
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            response = await self._http.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            name = type(exc).__name__
            detail = str(exc).strip()
            if isinstance(exc, httpx.TimeoutException):
                body = f"{name} after {timeout:g}s" + (f": {detail}" if detail else "")
            else:
                body = f"{name}: {detail}" if detail else name
            raise TyrMcpError(f"HTTP error calling Tyr ({method}): {body}") from exc

        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        if not response.content:
            return {}

        content_type = response.headers.get("Content-Type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(response.text)
        try:
            envelope = response.json()
        except ValueError as exc:
            raise TyrMcpError(f"Tyr returned invalid JSON for {method}") from exc
        if not isinstance(envelope, dict):
            raise TyrMcpError(f"Tyr returned a non-object response for {method}")
        return self._result(envelope, method)

    @classmethod
    def _result(cls, envelope: dict[str, Any], method: str) -> dict[str, Any]:
        error = envelope.get("error")
        if error is not None:
            if isinstance(error, dict):
                code = error.get("code", "unknown")
                message = error.get("message", error)
                raise TyrMcpError(f"MCP {code}: {message}")
            raise TyrMcpError(f"MCP error calling {method}: {error}")
        result = envelope.get("result", {})
        if not isinstance(result, dict):
            raise TyrMcpError(f"Tyr returned a non-object result for {method}")
        return cast(dict[str, Any], result)

    @classmethod
    def _parse_sse(cls, text: str) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                envelope = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(envelope, dict):
                if "result" in envelope or "error" in envelope:
                    last = cls._result(envelope, "SSE event")
        return last

    async def initialize(self) -> dict[str, Any]:
        result = await self._post(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gamr", "version": "0.1.0"},
            },
        )
        await self._post("notifications/initialized")
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._post("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise TyrMcpError("Tyr tools/list returned a non-list tools value")
        return [cast(dict[str, Any], tool) for tool in tools if isinstance(tool, dict)]

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object],
        *,
        timeout: float = TOOL_CALL_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        result = await self._post(
            "tools/call",
            {"name": name, "arguments": dict(arguments)},
            timeout=timeout,
        )
        content = result.get("content", [])
        if not isinstance(content, list):
            return result
        text_parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        raw = "\n".join(text_parts)
        if not raw:
            return result
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {"text": raw}
        return cast(dict[str, Any], decoded) if isinstance(decoded, dict) else {"value": decoded}

    async def start_conversation(
        self,
        *,
        idempotency_key: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {"idempotencyKey": idempotency_key or str(uuid4())}
        if title is not None:
            arguments["title"] = title
        return await self.call_tool("tyr_assistant_start_conversation", arguments)

    async def query(
        self,
        message: str,
        *,
        operation_id: str | None = None,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "message": message,
            "idempotencyKey": idempotency_key or str(uuid4()),
        }
        if operation_id:
            arguments["operationId"] = operation_id
        if conversation_id:
            arguments["conversationId"] = conversation_id
        return await self._call_assistant("tyr_assistant_query", arguments)

    async def request(
        self,
        message: str,
        *,
        operation_id: str | None = None,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "message": message,
            "idempotencyKey": idempotency_key or str(uuid4()),
        }
        if operation_id:
            arguments["operationId"] = operation_id
        if conversation_id:
            arguments["conversationId"] = conversation_id
        return await self._call_assistant("tyr_assistant_request", arguments)

    async def _call_assistant(self, name: str, arguments: dict[str, object]) -> dict[str, Any]:
        scope = self._bridge_scope(arguments)
        previous = self._bridge_observations.get(scope, {}).copy()
        result = await self.call_tool(name, arguments)
        operation_id = result.get("operationId") or arguments.get("operationId")
        if not scope[1]:
            scope = self._bridge_scope(result)
            previous = self._bridge_observations.get(scope, {}).copy()
        if isinstance(operation_id, str):
            self._bridge_requests[operation_id] = (scope, previous)
        if scope[1]:
            self._bridge_observations.setdefault(scope, {}).update(bridge_snapshot(result))
        return result

    @staticmethod
    def _bridge_scope(payload: dict[str, object]) -> tuple[str, str]:
        for key in ("conversationId", "operationId"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return key, value
        return "operationId", ""

    async def operation_status(self, operation_id: str, *, wait_seconds: int = 0) -> dict[str, Any]:
        return await self.call_tool(
            "tyr_operation_status",
            {"operationId": operation_id, "waitSeconds": wait_seconds},
            timeout=wait_seconds + 60,
        )

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        """Settle work while promoting only bridge replies fresh for this request."""

        op_id = result.get("operationId")
        if not isinstance(op_id, str):
            op_id = operation_id
        if not isinstance(op_id, str):
            return result
        context = self._bridge_requests.pop(op_id, None)
        if context is None:
            scope = ("operationId", op_id)
            previous = self._bridge_observations.get(scope, {}).copy()
        else:
            scope, previous = context
        observed = self._bridge_observations.setdefault(scope, {})
        observed.update(bridge_snapshot(result))

        async def read_status(wait: int) -> dict[str, object]:
            status = await self.operation_status(op_id, wait_seconds=wait)
            observed.update(bridge_snapshot(status))
            return status

        settled = await settle_operation(
            read_status,
            initial=result,
            previous_bridges=previous,
        )
        payload = dict(settled.payload)
        settlement: dict[str, object] = {
            "state": settled.local_state,
            "notes": list(settled.notes),
        }
        if settled.reply is not None:
            settlement["reply"] = settled.reply
        payload["gamrSettlement"] = settlement
        return payload

    async def resolve_approval(
        self,
        operation_id: str,
        approval_id: str,
        approval_type: str,
        decision: str,
        *,
        custom_response: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "operationId": operation_id,
            "approvalId": approval_id,
            "approvalType": approval_type,
            "decision": decision,
            "idempotencyKey": idempotency_key or str(uuid4()),
        }
        if custom_response:
            arguments["customResponse"] = custom_response
        return await self.call_tool("tyr_approval_resolve", arguments)

    async def bridge_list(self) -> dict[str, Any]:
        return await self.call_tool("tyr_workspace_bridge_list", {})

    async def bridge_send(
        self,
        bridge_id: str,
        message: str,
        *,
        conversation_id: str | None = None,
        wait_seconds: int = 0,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "bridgeId": bridge_id,
            "message": message,
            "waitSeconds": wait_seconds,
            "idempotencyKey": idempotency_key or str(uuid4()),
        }
        if conversation_id:
            arguments["conversationId"] = conversation_id
        return await self.call_tool(
            "tyr_workspace_bridge_send",
            arguments,
            timeout=wait_seconds + 60,
        )

    async def bridge_status(
        self, bridge_request_id: str, *, wait_seconds: int = 0
    ) -> dict[str, Any]:
        return await self.call_tool(
            "tyr_workspace_bridge_status",
            {"bridgeRequestId": bridge_request_id, "waitSeconds": wait_seconds},
            timeout=wait_seconds + 60,
        )

    async def bridge_history(
        self,
        bridge_id: str,
        conversation_id: str,
        *,
        limit: int = 30,
        before: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "bridgeId": bridge_id,
            "conversationId": conversation_id,
            "limit": limit,
        }
        if before:
            arguments["before"] = before
        return await self.call_tool(
            "tyr_workspace_bridge_history",
            arguments,
        )
