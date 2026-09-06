from __future__ import annotations

import json
from datetime import UTC, datetime

from ..ports.artifacts import ArtifactStore
from .activity import RunEvents
from .artifacts import write_checkpoint, write_event, write_raw, write_transcript
from .conversation_state import ConversationState, TurnContext, observe_reply
from .records import TargetConversation
from .target_exchange import TargetExchange


def judge_observed_facts(result: dict[str, object]) -> dict[str, object]:
    facts: dict[str, object] = {}
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
    if full_reply and conversation.seen_reply and full_reply.startswith(conversation.seen_reply):
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
    events.emit(
        "target.completed",
        context.run_id,
        phase=context.phase,
        case_id=context.case_id,
        turn=context.turn,
        turn_id=exchange.turn_id,
        detail=reply,
        fields=(("replySource", reply_source),) if reply_source else None,
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
    )
    settlement = result.get("gamrSettlement")
    if isinstance(settlement, dict) and settlement.get("state") in {
        "waiting_for_approval",
        "timeout",
    }:
        return f"Tyr operation is {settlement.get('state')}"
    return None
