from __future__ import annotations

import json
from datetime import UTC, datetime

from ..ports.artifacts import ArtifactStore
from .activity import RunEvents
from .artifacts import write_checkpoint, write_event, write_raw, write_transcript
from .conversation_state import ConversationState, TurnContext, observe_reply
from .records import TargetConversation
from .target_exchange import TargetExchange


def _settled_bridge_facts(result: dict[str, object]) -> dict[str, object]:
    settlement = result.get("gamrSettlement")
    reply = settlement.get("reply") if isinstance(settlement, dict) else None
    bridges = result.get("bridges")
    if not isinstance(reply, str) or not isinstance(bridges, list):
        return {}
    bridge = next(
        (
            item
            for item in reversed(bridges)
            if isinstance(item, dict) and item.get("response") == reply
        ),
        None,
    )
    if bridge is None:
        return {}
    keys = {
        "bridgeRequestId": "bridgeRequestId",
        "bridgeId": "bridgeId",
        "conversationId": "bridgeConversationId",
        "peerWorkspaceName": "bridgePeerWorkspace",
        "acknowledgement": "bridgeAcknowledgement",
    }
    facts: dict[str, object] = {
        output_key: value
        for input_key, output_key in keys.items()
        if isinstance(value := bridge.get(input_key), str)
    }
    state = bridge.get("state") or bridge.get("status")
    if isinstance(state, str):
        facts["bridgeState"] = state
    facts["bridgeResponseRecorded"] = bool(reply.strip())
    return facts


def judge_observed_facts(result: dict[str, object]) -> dict[str, object]:
    facts: dict[str, object] = {}
    operation_id = result.get("operationId")
    if isinstance(operation_id, str):
        facts["operationId"] = operation_id
    state = result.get("state")
    if isinstance(state, str):
        facts["targetState"] = state
    settlement = result.get("gamrSettlement")
    if isinstance(settlement, dict):
        settlement_state = settlement.get("state")
        if isinstance(settlement_state, str):
            facts["settlementState"] = settlement_state
        pending = settlement.get("pendingApprovals")
        if isinstance(pending, list):
            facts["pendingApprovalCount"] = len(pending)
    pending = result.get("pendingApprovals")
    if isinstance(pending, list):
        facts["pendingApprovalCount"] = len(pending)
    executions = result.get("executions")
    if isinstance(executions, list):
        states = [
            value
            for item in executions
            if isinstance(item, dict)
            for value in (item.get("state") or item.get("status"),)
            if isinstance(value, str)
        ]
        facts["executionCount"] = len(executions)
        facts["executionStates"] = states
    facts.update(_settled_bridge_facts(result))
    return facts


def _resolved_reply(
    result: dict[str, object], conversation: TargetConversation
) -> tuple[str, str | None, int]:
    settlement_metadata = result.get("gamrSettlement")
    settlement_reply = (
        settlement_metadata.get("reply") if isinstance(settlement_metadata, dict) else None
    )
    reply_source: str | None = None
    if isinstance(settlement_reply, str) and settlement_reply.strip():
        full_reply = settlement_reply.strip()
        reply_source = "delegated bridge follow-up"
    else:
        full_reply = str(result.get("response") or "").strip()
    settlement_state = (
        settlement_metadata.get("state") if isinstance(settlement_metadata, dict) else None
    )
    approval_pending = isinstance(settlement_state, str) and settlement_state in {
        "peer_approval_blocked",
        "waiting_for_approval",
    }
    if (
        full_reply
        and conversation.seen_reply
        and full_reply.startswith(conversation.seen_reply)
        and not approval_pending
        and reply_source is None
    ):
        reply = full_reply[len(conversation.seen_reply) :].strip()
        replayed_chars = len(full_reply) - len(reply)
    else:
        reply = full_reply or str(result.get("message") or result)
        replayed_chars = 0
    if full_reply:
        conversation.seen_reply = full_reply
    if full_reply and not reply:
        reply = "[GAMR: Tyr published no new content this turn; treat the reply as pending.]"
    return reply, reply_source, replayed_chars


def record_target_reply(
    exchange: TargetExchange,
    conversation: TargetConversation,
    state: ConversationState,
    context: TurnContext,
    *,
    events: RunEvents,
    artifacts: ArtifactStore | None,
) -> str | None:
    result = exchange.result
    reply, reply_source, replayed_chars = _resolved_reply(result, conversation)
    settlement = result.get("gamrSettlement")
    settlement_state = settlement.get("state") if isinstance(settlement, dict) else None
    fields: tuple[tuple[str, str], ...] = (("replySource", reply_source),) if reply_source else ()
    if isinstance(settlement_state, str) and settlement_state in {
        "peer_approval_blocked",
        "waiting_for_approval",
        "timeout",
    }:
        fields += (("settlementState", settlement_state),)
    events.emit(
        "target.completed",
        context.run_id,
        phase=context.phase,
        case_id=context.case_id,
        turn=context.turn,
        turn_id=exchange.turn_id,
        detail=reply,
        fields=fields or None,
        metadata_extra=dict(fields),
    )
    reply = observe_reply(state, exchange.message, reply)
    replied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    state.transcript.append(
        {
            "role": "user",
            "content": reply,
            "turnId": exchange.turn_id,
            "occurredAt": replied_at,
            "observedFacts": json.dumps(judge_observed_facts(result), separators=(",", ":")),
        }
    )
    write_raw(
        artifacts,
        context.run_id,
        exchange.turn_id,
        {
            "phase": context.phase_prompt[:120],
            "scenarioId": context.case_id,
            "scenarioExecutionId": context.scenario_execution_id,
            "model": {"content": exchange.content},
            "targetRequest": {
                "message": exchange.message,
                "operationId": conversation.operation_id,
                "conversationId": conversation.conversation_id,
                "idempotencyKey": exchange.idempotency_key,
            },
            "conversationStartRequest": {
                "idempotencyKey": exchange.conversation_start_idempotency_key
            },
            "conversationStart": exchange.conversation_start,
            "targetResponse": result,
            "stuckStreak": state.stuck_streak,
            "retryStreak": state.retry_streak,
            "replayedChars": replayed_chars,
        },
    )
    write_transcript(
        artifacts,
        context.run_id,
        [
            {
                "turnId": exchange.turn_id,
                "turn": context.turn,
                "role": "user",
                "content": reply,
                "scenarioId": context.case_id,
                "scenarioExecutionId": context.scenario_execution_id,
                "stage": context.phase,
                "caseId": context.case_id,
                "settlement": result.get("gamrSettlement"),
                "occurredAt": replied_at,
            }
        ],
    )
    write_checkpoint(
        artifacts,
        context.run_id,
        {
            "runId": context.run_id,
            "scenarioId": context.case_id,
            "scenarioExecutionId": context.scenario_execution_id,
            "phase": context.phase_prompt[:120],
            "turnId": exchange.turn_id,
            "operationId": conversation.operation_id,
            "conversationId": conversation.conversation_id,
            "pendingExternalCall": False,
            "idempotencyKey": exchange.idempotency_key,
        },
    )
    write_event(
        artifacts,
        context.run_id,
        {
            "runId": context.run_id,
            "eventType": "turn.completed",
            "turnId": exchange.turn_id,
            "operationId": conversation.operation_id,
        },
    )
    events.emit(
        "turn.completed",
        context.run_id,
        phase=context.phase,
        case_id=context.case_id,
        turn=context.turn,
        turn_id=exchange.turn_id,
        fields=fields or None,
        metadata_extra=dict(fields),
    )
    settlement = result.get("gamrSettlement")
    if isinstance(settlement, dict) and settlement.get("state") in {
        "waiting_for_approval",
        "timeout",
    }:
        return f"Tyr operation is {settlement.get('state')}"
    return None
