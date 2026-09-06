from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from gamr_core import ExperimentPresetConfig, NextTurnDecision

from ..ports.artifacts import ArtifactStore
from ..ports.targets import TargetGateway
from .activity import RunEvents
from .artifacts import write_checkpoint, write_raw, write_transcript
from .conversation_state import TurnContext
from .records import PhaseResult, TargetConversation


@dataclass(frozen=True)
class TargetExchange:
    turn_id: str
    message: str
    content: str
    idempotency_key: str
    conversation_start_idempotency_key: str | None
    conversation_start: dict[str, object] | None
    result: dict[str, object]


async def send_target_message(
    target: TargetGateway,
    config: ExperimentPresetConfig,
    conversation: TargetConversation,
    context: TurnContext,
    transcript: list[dict[str, str]],
    decision: NextTurnDecision,
    content: str,
    *,
    events: RunEvents,
    artifacts: ArtifactStore | None,
) -> TargetExchange | PhaseResult:
    message = decision.message or ""
    turn_id = str(uuid4())
    requested_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    transcript.append(
        {
            "role": "assistant",
            "content": message,
            "turnId": turn_id,
            "occurredAt": requested_at,
        }
    )
    write_transcript(
        artifacts,
        context.run_id,
        [
            {
                "turnId": turn_id,
                "turn": context.turn,
                "role": "assistant",
                "content": message,
                "stage": context.phase,
                "caseId": context.case_id,
                "scenarioId": context.case_id,
                "scenarioExecutionId": context.scenario_execution_id,
                "occurredAt": requested_at,
            }
        ],
    )
    idempotency_key = str(uuid4())
    conversation_start: dict[str, object] | None = None
    conversation_start_idempotency_key: str | None = None
    try:
        if conversation.conversation_id is None:
            conversation_start_idempotency_key = str(uuid4())
            conversation_start = await target.start_conversation(
                idempotency_key=conversation_start_idempotency_key
            )
            conversation_id = conversation_start.get("conversationId")
            if not isinstance(conversation_id, str) or not conversation_id:
                raise ValueError("Tyr conversation start returned no conversationId")
            conversation.conversation_id = conversation_id
        write_checkpoint(
            artifacts,
            context.run_id,
            {
                "runId": context.run_id,
                "phase": context.phase_prompt[:120],
                "turnId": turn_id,
                "operationId": conversation.operation_id,
                "conversationId": conversation.conversation_id,
                "pendingExternalCall": True,
                "idempotencyKey": idempotency_key,
            },
        )
        events.emit(
            "target.requesting",
            context.run_id,
            phase=context.phase,
            case_id=context.case_id,
            turn=context.turn,
            turn_id=turn_id,
            metadata_extra={"conversationId": conversation.conversation_id},
            detail=message,
        )
        if config.action_mode == "approval_required":
            result = await target.request(
                message,
                operation_id=conversation.operation_id,
                conversation_id=conversation.conversation_id,
                idempotency_key=idempotency_key,
            )
        else:
            result = await target.query(
                message,
                operation_id=conversation.operation_id,
                conversation_id=conversation.conversation_id,
                idempotency_key=idempotency_key,
            )
        new_operation_id = result.get("operationId")
        if isinstance(new_operation_id, str):
            conversation.operation_id = new_operation_id
        result = await target.settle(result, operation_id=conversation.operation_id)
    except Exception as exc:
        events.emit(
            "target.failed",
            context.run_id,
            phase=context.phase,
            case_id=context.case_id,
            turn=context.turn,
            turn_id=turn_id,
            detail=type(exc).__name__,
        )
        write_raw(
            artifacts,
            context.run_id,
            turn_id,
            {
                "phase": context.phase_prompt[:120],
                "model": {"content": content},
                "targetRequest": {
                    "message": message,
                    "operationId": conversation.operation_id,
                    "conversationId": conversation.conversation_id,
                    "idempotencyKey": idempotency_key,
                },
                "conversationStartRequest": {
                    "idempotencyKey": conversation_start_idempotency_key
                },
                "conversationStart": conversation_start,
                "error": str(exc),
            },
        )
        return PhaseResult(
            transcript,
            conversation.operation_id,
            decision,
            [],
            f"target call failed: {exc}",
        )
    return TargetExchange(
        turn_id,
        message,
        content,
        idempotency_key,
        conversation_start_idempotency_key,
        conversation_start,
        result,
    )
