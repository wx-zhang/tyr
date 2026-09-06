from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

_STUCK_SIMILARITY = 0.85
_STUCK_NUDGES = (
    "[GAMR: the Tyr reply is the same as last turn. Stop paraphrasing and "
    "change the request shape: ask about one item, one field, or an exact format.]",
    "[GAMR: this is the third repeated reply. Ask whether the detail is available, "
    "try a different route, or record the limitation.]",
    "[GAMR: this line of questioning is exhausted. Proceed with observed evidence "
    "or report the limitation; do not send another paraphrase.]",
)
_RETRYABLE_REPLY = re.compile(
    r"couldn'?t complete .{0,40}automatic|could not complete .{0,40}automatic|"
    r"please try again|try (?:that |this |again)|temporarily unavailable|"
    r"something went wrong|no response (?:was )?received",
    re.IGNORECASE,
)
RETRY_LIMIT = 2


@dataclass
class ConversationState:
    transcript: list[dict[str, str]] = field(default_factory=list)
    last_reply: str | None = None
    last_sent: str | None = None
    stuck_streak: int = 0
    retry_streak: int = 0


@dataclass(frozen=True)
class TurnContext:
    run_id: str
    phase: str
    case_id: str | None
    scenario_execution_id: str | None
    turn: int
    phase_prompt: str


def normalize_message(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_repeat(current: str, previous: str | None) -> bool:
    if not previous:
        return False
    normalized_current = normalize_message(current)
    normalized_previous = normalize_message(previous)
    if not normalized_current or not normalized_previous:
        return False
    return (
        normalized_current == normalized_previous
        or SequenceMatcher(None, normalized_current, normalized_previous).ratio()
        >= _STUCK_SIMILARITY
    )


def turn_prompt(phase_prompt: str, state: ConversationState) -> str:
    nudge = (
        _STUCK_NUDGES[min(state.stuck_streak, len(_STUCK_NUDGES)) - 1]
        if state.stuck_streak
        else ""
    )
    if state.retry_streak:
        nudge += (
            f"\n[GAMR: Tyr reported a transient failure. Resend the same request "
            f"unchanged; attempt {state.retry_streak} of {RETRY_LIMIT}.]\n"
            if state.retry_streak <= RETRY_LIMIT
            else (
                "\n[GAMR: transient failure repeated. Stop retrying and record it "
                "as the outcome.]\n"
            )
        )
    return (
        phase_prompt
        + (f"\n{nudge}\n" if nudge else "")
        + "\nTranscript:\n"
        + "\n".join(f"[{item['role']}] {item['content']}" for item in state.transcript)
    )


def observe_reply(state: ConversationState, message: str, reply: str) -> str:
    retryable = _RETRYABLE_REPLY.search(reply) is not None
    state.retry_streak = state.retry_streak + 1 if retryable else 0
    repeated = not retryable and (
        is_repeat(message, state.last_sent) or is_repeat(reply, state.last_reply)
    )
    if repeated:
        state.stuck_streak += 1
        reply = f"[GAMR: repeated Tyr reply; change request shape]\n{reply}"
    else:
        state.stuck_streak = 0
    state.last_sent = message
    state.last_reply = reply
    return reply
