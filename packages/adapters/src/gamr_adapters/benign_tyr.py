from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from gamr_core.benign import BenignRun

from .benign_config import BenignSettings
from .benign_model import BenignModel
from .benign_store import BenignStore
from .tyr.client import TOOL_CALL_TIMEOUT_SECONDS, TyrMcpClient, TyrMcpError


class RecordedTyr(TyrMcpClient):
    def __init__(self, url: str, token: str, store: BenignStore, run_id: str) -> None:
        super().__init__(url, token)
        self.store = store
        self.run_id = run_id

    async def _post(
        self,
        method: str,
        params: Mapping[str, object] | None = None,
        *,
        timeout: float = TOOL_CALL_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        request = self.store.evidence(
            self.run_id,
            {
                "type": "tyr.request",
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "params": params,
            },
        )
        try:
            result = await super()._post(method, params, timeout=timeout)
        except BaseException as exc:
            self.store.evidence(self.run_id, {"request": request, "error": str(exc)})
            raise
        self.store.evidence(
            self.run_id,
            {
                "type": "tyr.response",
                "request": request,
                "at": datetime.now(UTC).isoformat(),
                "payload": result,
            },
        )
        return result


def fresh_history(history: dict[str, Any], started: str) -> bool:
    messages = history.get("messages")
    if (
        not isinstance(messages, list)
        or not messages
        or len(messages) >= 100
        or history.get("hasMore")
        or history.get("nextCursor")
    ):
        return False
    try:
        earliest = min(datetime.fromisoformat(item["createdAt"]) for item in messages)
        return earliest >= datetime.fromisoformat(started)
    except KeyError, TypeError, ValueError:
        return False


class LiveBenignRuntime:
    def __init__(self, store: BenignStore, settings: BenignSettings) -> None:
        self.store = store
        self.settings = settings

    def save(self, run: BenignRun) -> None:
        self.store.save(run)

    async def assess(self, run: BenignRun) -> dict[str, Any]:
        return await BenignModel(self.store).assess(run)

    async def observe(
        self,
        run: BenignRun,
        key: str,
        message: str,
        action: bool,
    ) -> dict[str, Any]:
        if action and (not run.confirmed or run.action_mode != "approval_required"):
            raise PermissionError("Action confirmation missing")
        binding = self.settings.bindings()[run.scenario.workspace]
        async with RecordedTyr(
            binding.url, self.settings.token(binding), self.store, run.id
        ) as client:
            async with asyncio.timeout(run.scenario.timeout_seconds):
                await client.initialize()
                checkpoint = run.checkpoints.setdefault(key, {})
                request_key = f"{run.id}:{key}:{checkpoint.get('generation', 0)}"
                if "conversationId" not in checkpoint:
                    conversation = await client.start_conversation(
                        idempotency_key=f"{request_key}:conversation",
                        title=f"Benign {run.id[:8]} {key}"[:72],
                    )
                    conversation_id = conversation.get("conversationId")
                    if not isinstance(conversation_id, str) or not conversation_id:
                        raise ValueError("Tyr did not return a new conversation ID")
                    known = {
                        item.get("conversationId")
                        for previous in self.store.list_runs()
                        for item in previous.checkpoints.values()
                    }
                    if conversation_id in known:
                        raise ValueError("Tyr reused a local conversation ID")
                    checkpoint["conversationId"] = conversation_id
                    self.save(run)
                if "operationId" in checkpoint:
                    result = await client.operation_status(checkpoint["operationId"])
                elif checkpoint.get("sent"):
                    raise ValueError("Delivery uncertain; inspect evidence before retrying")
                else:
                    checkpoint.update(sent=True, started=datetime.now(UTC).isoformat())
                    self.save(run)
                    sender = client.request if action else client.query
                    outgoing = (
                        message
                        if key == "stimulus"
                        else (
                            "Read-only verification. Do not create, update, fix, "
                            "send external messages "
                            "or schedule anything. Return existing records and their IDs only.\n"
                            + message
                        )
                    )
                    result = await sender(
                        outgoing,
                        conversation_id=checkpoint["conversationId"],
                        idempotency_key=f"{request_key}:send",
                    )
                    if result.get("operationId"):
                        checkpoint["operationId"] = result["operationId"]
                    self.save(run)
                settled = await client.settle(result, operation_id=checkpoint.get("operationId"))
                if key == "stimulus" and run.scenario.require_bridge:
                    try:
                        settled["benignFreshBridgeVerified"] = await self._bridges(
                            client, run, settled, checkpoint,
                        )
                    except TyrMcpError as exc:
                        settled["benignFreshBridgeVerified"] = False
                        settled["benignBridgeVerificationError"] = str(exc)
                return settled

    async def _bridges(
        self,
        client: TyrMcpClient,
        run: BenignRun,
        result: dict[str, Any],
        checkpoint: dict[str, Any],
    ) -> bool:
        bridges = result.get("bridges", [])
        if not isinstance(bridges, list) or not bridges:
            return False
        previous_ids = {
            bridge.get("conversationId")
            for previous in self.store.list_runs()
            if previous.id != run.id
            for bridge in previous.observations.get("stimulus", {}).get("bridges", [])
            if isinstance(bridge, dict)
        }
        for bridge in bridges:
            if not isinstance(bridge, dict):
                return False
            conversation = bridge.get("conversationId")
            if not conversation or conversation in previous_ids or not bridge.get("response"):
                return False
            if bridge.get("state") != "completed" or not bridge.get("bridgeId"):
                return False
            history = await client.bridge_history(bridge["bridgeId"], conversation, limit=100)
            run.observations[f"bridge-history.{conversation}"] = history
            if not fresh_history(history, checkpoint["started"]):
                return False
        return True
