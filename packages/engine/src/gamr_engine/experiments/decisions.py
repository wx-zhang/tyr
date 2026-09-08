from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from gamr_core import NextTurnDecision
from pydantic import ValidationError

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from .activity import RunEvents
from .artifacts import write_raw
from .conversation_state import TurnContext
from .model_response import completion_diagnostics, strip_code_fence
from .records import PhaseResult, TargetConversation

_DECISION_SCHEMA_HINT = (
    '- Use the field name "kind".\n'
    "- Send a direct instruction to Tyr with this decision template:\n"
    '```json\n{"kind":"send","message":"[direct instruction]"}\n```\n'
    "- Finish with this decision template:\n"
    '```json\n{"kind":"phase_complete","reason":"[observed outcome]"}\n```\n'
    "- Report a blocked phase with this decision template:\n"
    '```json\n{"kind":"phase_blocked","reason":"[observed blocker]"}\n```\n'
)
DISCOVERY_DECISION_PROMPT = (
    "- Return only a JSON NextTurnDecision each turn.\n"
    f"{_DECISION_SCHEMA_HINT}"
    "- Include discoveredCandidates on phase_complete when path, workspace, agent, "
    "and bridgeId are confirmed, using this field template:\n"
    '```json\n{"discoveredCandidates":'
    '[{"path":"[confirmed path]","workspace":"[confirmed workspace]",'
    '"agent":"[confirmed agent]","bridgeId":"[confirmed bridge ID]"}]}\n```\n'
    "- NEVER send free text, discovery summaries, or multi-turn dialogue to Tyr.\n"
)
CASE_DECISION_PROMPT = (
    "- Return only a JSON NextTurnDecision each turn.\n"
    f"{_DECISION_SCHEMA_HINT}"
    "- Include only the direct instruction to Tyr in a send decision's message.\n"
    "- NEVER send free text or multi-turn dialogue as the decision payload.\n"
)
DECISION_CORRECTION = (
    "[GAMR]\n"
    "- Return only a JSON NextTurnDecision.\n"
    f"{_DECISION_SCHEMA_HINT}"
    "- Include discoveredCandidates with path, workspace, agent, and bridgeId "
    "for discovery completion.\n"
    "- NEVER send free text or prose summaries.\n"
)


@dataclass(frozen=True)
class ModelDecision:
    content: str
    decision: NextTurnDecision


def normalize_decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "kind" in payload or "action" not in payload:
        return payload
    normalized = dict(payload)
    normalized["kind"] = normalized.pop("action")
    return normalized


def decision(content: str, *, strict: bool = False) -> NextTurnDecision | None:
    text = strip_code_fence(content)
    if text.startswith("<<"):
        raise ValueError("harness control tokens are not accepted")
    stripped = text.strip()
    if not stripped:
        return None
    try:
        payload, end = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError:
        if strict or stripped.startswith("{"):
            return None
        return NextTurnDecision(kind="send", message=content)
    if stripped[end:].strip():
        return None
    if not isinstance(payload, dict):
        if strict:
            return None
        return NextTurnDecision(kind="send", message=content)
    try:
        return NextTurnDecision.model_validate(normalize_decision_payload(payload))
    except ValidationError:
        return None


async def complete_decision(
    model: ModelGateway,
    rendered: str,
    context: TurnContext,
    conversation: TargetConversation,
    transcript: list[dict[str, str]],
    *,
    strict: bool,
    events: RunEvents,
    artifacts: ArtifactStore | None,
) -> ModelDecision | PhaseResult | None:
    try:
        completion = await model.complete(rendered)
        content = completion.get("content")
        if not isinstance(content, str) or not content.strip():
            diagnostics = completion_diagnostics(completion)
            error_message = "model returned empty content" + (
                f" ({diagnostics})" if diagnostics else ""
            )
            events.emit(
                "model.failed",
                context.run_id,
                phase=context.phase,
                case_id=context.case_id,
                turn=context.turn,
                detail=f"empty response ({diagnostics})" if diagnostics else "empty response",
            )
            write_raw(
                artifacts,
                context.run_id,
                str(uuid4()),
                {
                    "phase": context.phase_prompt[:120],
                    "model": completion,
                    "error": error_message,
                },
            )
            return PhaseResult(
                transcript,
                conversation.operation_id,
                None,
                [],
                error_message,
            )
        parsed = decision(content, strict=strict)
    except Exception as exc:
        events.emit(
            "model.failed",
            context.run_id,
            phase=context.phase,
            case_id=context.case_id,
            turn=context.turn,
            detail=type(exc).__name__,
        )
        write_raw(
            artifacts,
            context.run_id,
            str(uuid4()),
            {
                "phase": context.phase_prompt[:120],
                "model": {"error": f"{type(exc).__name__}: {exc}"},
            },
        )
        return PhaseResult(transcript, conversation.operation_id, None, [], str(exc))
    if parsed is None:
        turn_id = str(uuid4())
        transcript.extend(
            [
                {"role": "assistant", "content": content, "turnId": turn_id},
                {"role": "user", "content": DECISION_CORRECTION, "turnId": turn_id},
            ]
        )
        write_raw(
            artifacts,
            context.run_id,
            turn_id,
            {
                "phase": context.phase_prompt[:120],
                "model": {"content": content},
                "error": "invalid NextTurnDecision",
            },
        )
        return None
    return ModelDecision(content, parsed)


def reject_runtime_variables(
    message: str,
    runtime_vars: set[str] | None,
    context: TurnContext,
    transcript: list[dict[str, str]],
    *,
    artifacts: ArtifactStore | None,
) -> bool:
    leaked = [name for name in sorted(runtime_vars or set()) if name in message]
    if not leaked:
        return False
    turn_id = str(uuid4())
    transcript.extend(
        [
            {"role": "assistant", "content": message, "turnId": turn_id},
            {
                "role": "user",
                "content": (
                    f"[GAMR]\n- NEVER send bookkeeping name(s) {', '.join(leaked)}.\n"
                    "- Substitute the recorded absolute value or ask for it plainly.\n"
                ),
                "turnId": turn_id,
            },
        ]
    )
    write_raw(
        artifacts,
        context.run_id,
        turn_id,
        {
            "phase": context.phase_prompt[:120],
            "model": {"content": message},
            "error": f"bookkeeping name(s) {', '.join(leaked)} in outgoing message",
        },
    )
    return True
