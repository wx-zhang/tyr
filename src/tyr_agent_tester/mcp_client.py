#!/usr/bin/env python3
"""
Minimal JSON-RPC client for the Tyr Assistant MCP server (HTTP + SSE transport).

Wraps the eight tools Tyr exposes:
  - tyr_assistant_query    (read-only: status/inventory/capabilities questions)
  - tyr_assistant_request  (can trigger real agent/computer actions -- gated, see agent_loop.py)
  - tyr_operation_status   (poll/long-poll an operation until it settles)
  - tyr_approval_resolve   (approve/reject a pending management or runtime approval)
  - tyr_workspace_bridge_list / _send / _status / _history
                           (reach a connected peer workspace -- see below)

Note the split between the two assistant tools: `query` is server-enforced
read-only and must NOT be used to hand work to an Agent, even when the Agent's
downstream task only reads files. Every instruction or handoff goes through
`request`.

Cross-workspace access is mediated. A Bridge connects this workspace to a peer
*Tyr Assistant*, never to a peer Agent -- peer Agents are not addressable from
here. To act in another workspace you ask its Assistant to act for you, within
the Bridge's declared permissions (e.g. chat, task_delegation, topology_read).
"""

from __future__ import annotations

import json
import os
import uuid

import requests

MCP_URL = os.environ.get("TYR_MCP_URL", "https://www.tyr.ai/tyrcli/mcp")

# Read from env, never hardcode. Get it from Tyr Web -> account/developer
# settings, or browser DevTools (Network tab -> request to tyr.ai -> Authorization header).
TOKEN_ENV_VAR = "TYR_MCP_TOKEN"


class TyrMCPError(RuntimeError):
    pass


class TyrMCPClient:
    def __init__(self, url: str = MCP_URL, token: str | None = None):
        token = token or os.environ.get(TOKEN_ENV_VAR)
        if not token:
            raise TyrMCPError(
                f"Missing token: set the {TOKEN_ENV_VAR} environment variable before running."
            )
        self.url = url
        self._rpc_id = 0
        self._session_id = None
        self._http = requests.Session()
        self._http.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _post(self, method: str, params: dict | None = None, timeout: int = 60) -> dict:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params:
            payload["params"] = params
        if self._session_id:
            self._http.headers["Mcp-Session-Id"] = self._session_id

        try:
            resp = self._http.post(self.url, json=payload, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise TyrMCPError(f"HTTP error calling Tyr ({method}): {e}") from e

        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid

        ct = resp.headers.get("Content-Type", "")
        if "text/event-stream" in ct:
            return self._parse_sse(resp.text)

        data = resp.json()
        if "error" in data:
            raise TyrMCPError(f"MCP {data['error']['code']}: {data['error']['message']}")
        return data.get("result", {})

    @staticmethod
    def _parse_sse(text: str) -> dict:
        last = {}
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if "result" in event:
                    last = event["result"]
                elif "error" in event:
                    raise TyrMCPError(f"MCP error: {event['error']}")
        return last

    def initialize(self) -> dict:
        result = self._post("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tyr-loop-agent", "version": "1.0.0"},
        })
        try:
            self._http.post(
                self.url,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                timeout=10,
            )
        except requests.RequestException:
            pass
        return result

    def list_tools(self) -> list:
        return self._post("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict, timeout: int = 60) -> dict:
        """Call a tool and return its result as a dict (parsed from the text content block)."""
        result = self._post("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        content = result.get("content", [])
        text_parts = [c["text"] for c in content if c.get("type") == "text" and "text" in c]
        raw = "\n".join(text_parts)
        if not raw:
            return result
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"text": raw}

    # -- typed wrappers around the four Tyr tools -----------------------

    def query(self, message: str, operation_id: str | None = None) -> dict:
        """Read-only question (status/inventory/capabilities). Never mutates state."""
        args = {"message": message, "idempotencyKey": str(uuid.uuid4())}
        if operation_id:
            args["operationId"] = operation_id
        return self.call_tool("tyr_assistant_query", args)

    def request(self, message: str, operation_id: str | None = None) -> dict:
        """Management action / instruction to an Agent. Can have real side effects."""
        args = {"message": message, "idempotencyKey": str(uuid.uuid4())}
        if operation_id:
            args["operationId"] = operation_id
        return self.call_tool("tyr_assistant_request", args)

    def operation_status(self, operation_id: str, wait_seconds: int = 0) -> dict:
        # The server holds the connection open for up to wait_seconds on a
        # long-poll; give the client comfortable headroom above that so a
        # slightly slow response doesn't trip our own read timeout.
        return self.call_tool(
            "tyr_operation_status",
            {"operationId": operation_id, "waitSeconds": wait_seconds},
            timeout=wait_seconds + 60,
        )

    # -- Workspace Bridge tools ------------------------------------------
    # A Bridge reaches the peer workspace's Tyr Assistant. It never reaches a
    # peer Agent directly, and never exposes the peer's private chats.

    def bridge_list(self) -> dict:
        """Bridges authorized for this workspace: peer name, status
        (active/revoked), direction, and declared permissions."""
        return self.call_tool("tyr_workspace_bridge_list", {})

    def bridge_send(
        self,
        bridge_id: str,
        message: str,
        conversation_id: str | None = None,
        wait_seconds: int = 0,
    ) -> dict:
        """One request to the peer Tyr Assistant over an active Bridge. Reuse
        conversation_id to continue the same isolated Bridge topic."""
        args = {
            "bridgeId": bridge_id,
            "message": message,
            "idempotencyKey": str(uuid.uuid4()),
            "waitSeconds": wait_seconds,
        }
        if conversation_id:
            args["conversationId"] = conversation_id
        return self.call_tool("tyr_workspace_bridge_send", args, timeout=wait_seconds + 60)

    def bridge_status(self, bridge_request_id: str, wait_seconds: int = 0) -> dict:
        """State of one Bridge request. Peer approval blockers are reported but
        cannot be resolved from this side."""
        return self.call_tool(
            "tyr_workspace_bridge_status",
            {"bridgeRequestId": bridge_request_id, "waitSeconds": wait_seconds},
            timeout=wait_seconds + 60,
        )

    def bridge_history(
        self, bridge_id: str, conversation_id: str, limit: int = 30, before: str | None = None
    ) -> dict:
        """A bounded page from one isolated Bridge conversation."""
        args = {"bridgeId": bridge_id, "conversationId": conversation_id, "limit": limit}
        if before:
            args["before"] = before
        return self.call_tool("tyr_workspace_bridge_history", args)

    def resolve_approval(
        self,
        operation_id: str,
        approval_id: str,
        approval_type: str,
        decision: str,
        custom_response: str | None = None,
    ) -> dict:
        args = {
            "operationId": operation_id,
            "approvalId": approval_id,
            "approvalType": approval_type,
            "decision": decision,
        }
        if custom_response:
            args["customResponse"] = custom_response
        return self.call_tool("tyr_approval_resolve", args)
