#!/usr/bin/env python3
"""
Loop Agent <-> Tyr Assistant

Runs a small LLM ("Loop Agent") as a QA tester of Tyr Assistant,
in three phases:
  1. Discovery: locate `important.txt` in a workspace other than the
     current one, confirm the path, workspace name, and agent name.
  2. Execute: run the test cases against the confirmed file path, one case
     at a time, each in its own conversation.
  3. Report: write a Markdown QA report with emoji status markers.

The Loop Agent's own model calls go through OpenRouter's OpenAI-compatible
API, so you can drive it with any model your OpenRouter account can reach.
Tyr Assistant itself is still reached over its own MCP server (see
mcp_client.py) -- that connection is unchanged.

Required env vars:
  TYR_MCP_TOKEN       Tyr bearer token (see mcp_client.py for how to get one)
  OPENROUTER_API_KEY  OpenRouter API key for the Loop Agent's own model calls

Optional env vars are documented alongside the constants in CONFIG below.

Usage:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  export TYR_MCP_TOKEN=...
  export OPENROUTER_API_KEY=...
  python3 agent_loop.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import NamedTuple

try:
    # The `openai` package is just the OpenAI-compatible HTTP client OpenRouter
    # speaks; it says nothing about which model you run. Aliased so nothing in
    # this file implies the Loop Agent must be an OpenAI model -- point
    # TYR_LOOP_MODEL at any slug your OpenRouter account can reach.
    from openai import OpenAI as LoopAgentClient
except ImportError as e:
    sys.exit(
        f"Missing dependency ({e}). Install into THIS interpreter with:\n"
        f"  {sys.executable} -m pip install -r requirements.txt"
    )

from mcp_client import TyrMCPClient, TyrMCPError
from prompts import (
    TEST_CASES,
    case_heading,
    fill_target,
    render_case_report_prompt,
    render_discovery_prompt,
    render_execute_prompt,
    render_summary_prompt,
    runtime_variables,
)

# ─────────────────────────────────────────────────────────────
# CONFIG -- edit before running, or override via env vars
# ─────────────────────────────────────────────────────────────

# Control tokens the Loop Agent emits to signal a phase is over. They are
# harness signalling and must never be transmitted to Tyr -- converse() stops
# without sending as soon as one appears anywhere in the message.
STOP_TOKEN = "<<DONE>>"
DISCOVERY_DONE_PREFIX = "<<DISCOVERY_COMPLETE:"
DISCOVERY_FAILED_TOKEN = "<<DISCOVERY_FAILED>>"

# The target file lives under this directory by definition. Discovery discards
# any reported hit outside it -- see run_discovery(). Keep in step with the
# search scope stated in the discovery prompt.
SEARCH_ROOT = "/home"
# Discovery: locate the file in another workspace. Default: 20 turns. Keep the
# self-stop guidance in DISCOVERY_PROMPT_TEMPLATE in step with this -- the Loop
# Agent gives up on its own well before the budget if the prompt says a smaller
# number, so raising this alone would change nothing.
EXPLORE_TURNS = int(os.environ.get("TYR_LOOP_EXPLORE_TURNS", "20"))
# Execute: turns budgeted per test case. Cases run multi-turn verification;
# 400 turns comfortably covers one.
MAX_TURNS = int(os.environ.get("TYR_LOOP_MAX_TURNS", "400"))
# Per-turn completion budget. Rule-dense system prompts can push a reasoning-capable
# model to spend much of this on hidden thinking tokens before it ever emits the
# visible message -- if that happens, call_model() gets back an empty string. Bump
# this env var first; reasoning consumption doesn't shrink just because the prompt
# is shorter.
TURN_MAX_TOKENS = int(os.environ.get("TYR_LOOP_TURN_MAX_TOKENS", "16000"))
# OpenRouter model slug for the Loop Agent's brain -- any model your OpenRouter
# account can reach. See https://openrouter.ai/models for the full list.
MODEL = os.environ.get("TYR_LOOP_MODEL", "openai/gpt-4o-mini")
# MODEL = os.environ.get("TYR_LOOP_MODEL", "anthropic/claude-sonnet-5")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Safety: when False (default) the Loop Agent can only ask read-only questions
# (tyr_assistant_query). Most non-trivial test cases need this True to run at all
# -- tyr_assistant_request can hand real instructions to a dev-full-access Agent
# running on a real machine. Every individual action still needs a human approval
# (see resolve_pending_approvals below) before it actually executes.
ALLOW_ACTIONS = os.environ.get("TYR_LOOP_ALLOW_ACTIONS", "false").lower() == "true"

# How long to long-poll a not-yet-finished operation before giving up on it.
POLL_WAIT_SECONDS = 30
POLL_MAX_ATTEMPTS = 10
# A terminal management state is necessary but NOT sufficient: Tyr can still be
# publishing a delegated Agent's return, so the reply visible at that instant may
# be an acknowledgement ("Routed to Alice. I will report back here...") rather
# than the answer. After the operation first looks done, re-check with a short
# long-poll and only believe it once `updatedAt` stops moving. Raise this to
# widen the window at the cost of that many extra seconds per turn.
SETTLE_WAIT_SECONDS = 5

LOG_FILE = "tyr_qatestsearch_log.jsonl"
REPORT_PREFIX = "qatestsearch"

# Report generation feeds the WHOLE run transcript to the model in one call, and
# that call has the same context window as any other. A case that spirals (one
# observed run repeated the same "workspace topology" reply 78 times) blows the
# transcript past the window, the report call 400s, and the run ends with no
# findings write-up at all. Raising the output budget cannot help -- the cap is
# the endpoint's, shared by input+output -- so the transcript is deduped and
# then hard-clipped to fit under it. All three are env-overridable.
CONTEXT_TOKEN_LIMIT = int(os.environ.get("TYR_LOOP_CONTEXT_LIMIT", "128000"))
REPORT_MAX_TOKENS = int(os.environ.get("TYR_LOOP_REPORT_MAX_TOKENS", "16000"))
# Output allowance for ONE case's subsection -- a few paragraphs, not a document.
SECTION_MAX_TOKENS = int(os.environ.get("TYR_LOOP_SECTION_MAX_TOKENS", "2000"))
# Chars per token, for turning a token budget into a char budget without a
# model-specific tokenizer. Deliberately BELOW the usual ~4 for English prose:
# transcripts are dense with paths, JSON and markdown, which tokenize worse. At
# 4 a clipped report still came back over the limit (a 400 at 115,976 input
# tokens against a 112,000 budget), so the estimate has to err small.
CHARS_PER_TOKEN = 3.2

# Tyr operation states that mean "settled -- stop polling". Must stay aligned
# with Tyr's own terminal states (see the state table in README.md); anything
# missing here gets polled until POLL_MAX_ATTEMPTS runs out and is then handed
# to the Loop Agent as provisional, even though it was actually final.
# `partial` IS terminal -- it means the operation settled with a mix of
# successful and unsuccessful executions. `error` is not a Tyr state at all:
# send_to_tyr() substitutes it locally when an MCP call raises TyrMCPError.
# `rejected` is unconfirmed against Tyr's API and has never appeared in a run
# log -- kept because a wrongly-included terminal state costs nothing, while a
# wrongly-excluded one costs POLL_MAX_ATTEMPTS * POLL_WAIT_SECONDS of stalling.
TERMINAL_STATES = {"completed", "partial", "failed", "cancelled", "error", "rejected"}

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────


# One id per process, stamped on every line. The log is append-only across every
# run AND every ad-hoc smoke test that imports this module, so without it the
# only way to isolate a single run is to eyeball timestamps and guess where one
# ended. Grep `"runId": "<id>"` to pull exactly one run out.
RUN_ID = uuid.uuid4().hex[:8]


def log(entry: dict) -> None:
    entry = {
        "runId": RUN_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def loggable_raw(raw: dict) -> dict:
    """The turn's payload with the reply text replaced by its length.

    The full payload is logged because the tool schema doesn't pin down what an
    entry in executions[]/bridges[] looks like, and that shape is only learnable
    from real delegating turns. `response`, though, is already stored verbatim as
    `from_tyr` -- keeping both doubled the file, and on a run where Tyr returns a
    growing cumulative transcript it was most of the 3.8 MB."""
    if not isinstance(raw, dict) or "response" not in raw:
        return raw
    trimmed = dict(raw)
    trimmed["response"] = f"<{len(raw.get('response') or '')} chars -- see from_tyr>"
    return trimmed


class LoopAgentBlocked(RuntimeError):
    """The Loop Agent's own model produced no usable message.

    Distinct from an Agent under test refusing (see failure_notes): this is the
    QA tester itself being stopped -- by a provider safety filter, an exhausted
    token budget, or an API error -- so the turn never reached Tyr at all.
    Carries the provider's stated reason rather than a bare empty string."""

    def __init__(self, reason: str, detail: dict):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def completion_diagnostics(completion) -> dict:
    """What the provider said about how a completion turned out.

    Which fields are populated varies by provider and by model, so everything
    is read defensively and empties are dropped. `moderation` and
    `native_finish_reason` are OpenRouter additions on top of the OpenAI shape
    and are usually the most specific evidence of a safety block."""
    try:
        dump = completion.model_dump()
    except Exception:
        return {"unparsed": str(completion)[:500]}

    choice = (dump.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    detail = {
        "finishReason": choice.get("finish_reason"),
        "nativeFinishReason": choice.get("native_finish_reason"),
        "refusal": message.get("refusal"),
        "moderation": dump.get("moderation"),
        "error": dump.get("error"),
        "provider": dump.get("provider"),
        "model": dump.get("model"),
        "usage": dump.get("usage"),
        "spentOnReasoning": bool(message.get("reasoning")),
    }
    return {k: v for k, v in detail.items() if v not in (None, "", False, {}, [])}


def explain_block(detail: dict) -> str:
    """One sentence naming the exact reason, for the terminal and the log."""
    if detail.get("refusal"):
        return f"the model refused: {detail['refusal']}"

    finish = str(detail.get("finishReason") or "").lower()
    native = str(detail.get("nativeFinishReason") or "").lower()
    reasons = "/".join(r for r in dict.fromkeys((finish, native)) if r)

    if detail.get("moderation") or "content_filter" in (finish, native) or "safety" in native:
        moderation = detail.get("moderation")
        suffix = f" -- moderation: {json.dumps(moderation, ensure_ascii=False)[:300]}" if moderation else ""
        return f"blocked by a provider content filter (finish_reason={reasons or 'unstated'}){suffix}"

    if finish == "length":
        hint = (
            " -- reasoning tokens consumed the budget before any visible message; "
            "raise TYR_LOOP_TURN_MAX_TOKENS"
            if detail.get("spentOnReasoning") else " -- raise TYR_LOOP_TURN_MAX_TOKENS"
        )
        return f"hit the {TURN_MAX_TOKENS}-token completion budget{hint}"

    if detail.get("error"):
        return f"provider error: {json.dumps(detail['error'], ensure_ascii=False)[:300]}"

    return f"empty response with no stated reason (finish_reason={reasons or 'unknown'})"


def call_model(
    brain: "LoopAgentClient",
    messages: list[dict],
    max_tokens: int,
    system: str | None = None,
) -> str:
    """One Loop Agent model call via OpenRouter's OpenAI-compatible chat API.
    Prepends `system` as a system message when given.

    Raises LoopAgentBlocked, carrying the provider's stated reason, rather than
    returning an empty string -- a bare "" is indistinguishable between a safety
    block, an exhausted budget, and an API fault, and all three need reporting."""
    if system is not None:
        messages = [{"role": "system", "content": system}, *messages]

    try:
        completion = brain.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=messages,
        )
    except Exception as e:
        raise LoopAgentBlocked(
            f"API call failed -- {type(e).__name__}: {e}",
            {"exception": f"{type(e).__name__}: {e}"},
        ) from e

    choices = getattr(completion, "choices", None) or []
    text = ((choices[0].message.content if choices else None) or "").strip()
    if text:
        return text

    detail = completion_diagnostics(completion)
    raise LoopAgentBlocked(explain_block(detail), detail)


def resolve_pending_approvals(tyr: TyrMCPClient, operation_id: str, approvals: list) -> None:
    """Approvals gate real actions -- always ask a human, never auto-approve."""
    for approval in approvals:
        print("\n!! Tyr is waiting on an approval:")
        print(json.dumps(approval, indent=2))
        decision = input(
            "Approve this? [y]es / [n]o / [s]kip (leave pending): "
        ).strip().lower()
        if decision not in ("y", "n"):
            print("Skipping -- left pending.")
            continue
        tyr.resolve_approval(
            operation_id=operation_id,
            approval_id=approval.get("approvalId") or approval.get("id"),
            approval_type=approval.get("approvalType", "management"),
            decision="approve" if decision == "y" else "reject",
        )


class TyrReply(NamedTuple):
    """One settled (or abandoned) exchange with Tyr.

    outcome is why the wait ended, and the three cases need different handling:
      "settled"  -- terminal, no execution or bridge request still in flight,
                    nothing moved across a settle window. Safe to act on.
      "our_turn" -- Tyr is blocked on input from us. Polling can NEVER advance
                    this; the Loop Agent has to send the next message.
      "timeout"  -- ran out of polling budget. Provisional; may be incomplete.
    """
    text: str
    operation_id: str | None
    state: str
    outcome: str
    raw: dict
    notes: tuple[str, ...] = ()  # why a runtime/bridge didn't succeed, if it didn't


# Fields an execution/bridge entry might carry explaining why it didn't succeed.
# Tyr's tool schema doesn't declare the entry shape, so cast a wide net and use
# whatever is actually present. Ordered so identity reads before cause.
DIAGNOSTIC_KEYS = (
    "agentName", "agent", "computerName",
    "state", "status",
    "error", "errorMessage", "failureReason", "reason", "refusal", "blockReason",
    "detail", "details", "summary", "message",
)


def failure_notes(result: dict) -> tuple[str, ...]:
    """Explain any execution or bridge request that did not plainly succeed.

    This is where a safety refusal surfaces. `tyr_operation_status` states that
    "Downstream Agent output is never returned directly", so when an Agent
    declines on safety grounds the operation's public `response` can come back
    empty while the actual reason sits in its execution entry. Reading only
    `response` throws that away and the run records a blank -- indistinguishable
    from a timeout or a silent failure.

    Returns () on a clean run, so happy paths stay quiet."""
    notes = []
    for group in ("executions", "bridges"):
        for entry in result.get(group) or []:
            if not isinstance(entry, dict):
                notes.append(f"{group}: {entry!r}"[:400])
                continue

            state = str(entry.get("state") or entry.get("status") or "").lower()
            fields = {
                key: str(entry[key]).strip()
                for key in DIAGNOSTIC_KEYS
                if isinstance(entry.get(key), (str, int, float, bool)) and str(entry[key]).strip()
            }
            # Quiet when it plainly succeeded and carries no error text.
            cause_keys = set(fields) - {"agentName", "agent", "computerName", "state", "status"}
            if state == "completed" and not cause_keys:
                continue
            if not fields:
                # Unknown shape -- keep the raw entry rather than dropping it.
                notes.append(f"{group}: {json.dumps(entry, ensure_ascii=False)}"[:400])
                continue
            notes.append(f"{group}: " + ", ".join(f"{k}={v}" for k, v in fields.items())[:400])
    return tuple(notes)


def work_pending(result: dict) -> bool:
    """True only when work under this operation is positively still unfinished.

    Two things can outlive the outer operation's own state:
      `executions` -- per-Agent runtime statuses. The operation can read
                      terminal while a delegated execution is still running.
      `bridges`    -- requests sent to a peer workspace's Tyr Assistant, which
                      round-trip through that peer (and may sit behind a peer
                      approval we cannot see or resolve from this side).

    Neither entry shape is pinned by the tool schemas, so this fails OPEN: an
    entry we cannot parse counts as not-pending. Guessing the other way would
    stall every turn until the poll budget ran out -- the same failure mode
    that a missing terminal state causes."""
    for group in ("executions", "bridges"):
        for entry in result.get(group) or []:
            if not isinstance(entry, dict):
                continue
            state = entry.get("state") or entry.get("status")
            if isinstance(state, str) and state.lower() not in TERMINAL_STATES:
                return True
    return False


def send_to_tyr(tyr: TyrMCPClient, message: str, operation_id: str | None) -> TyrReply:
    """Send one message to Tyr and wait for it to genuinely finish."""
    send = tyr.request if ALLOW_ACTIONS else tyr.query
    result = send(message, operation_id=operation_id)
    op_id = result.get("operationId", operation_id)

    outcome = "timeout"
    quiet_stamp = None  # updatedAt seen when the operation first looked done

    for _ in range(POLL_MAX_ATTEMPTS):
        state = result.get("state", "unknown")

        if state == "input_required":
            outcome = "our_turn"
            break

        approvals = result.get("pendingApprovals") or []
        if approvals and op_id:
            resolve_pending_approvals(tyr, op_id, approvals)
            result = tyr.operation_status(op_id, wait_seconds=POLL_WAIT_SECONDS)
            continue

        done = state in TERMINAL_STATES and not work_pending(result)
        if done and result.get("updatedAt") == quiet_stamp:
            outcome = "settled"  # a full settle window passed with no movement
            break

        # Looks done -> re-check briefly to catch a late-published return.
        # Still working -> go back to the long poll.
        quiet_stamp = result.get("updatedAt") if done else None
        result = tyr.operation_status(
            op_id, wait_seconds=SETTLE_WAIT_SECONDS if done else POLL_WAIT_SECONDS
        )

    # Budget can run out mid-settle on an operation that had in fact finished.
    if outcome == "timeout" and result.get("state") in TERMINAL_STATES and not work_pending(result):
        outcome = "settled"

    notes = failure_notes(result)
    text = (result.get("response") or "").strip()

    if not text:
        # No published reply. Prefer a concrete runtime reason (a safety refusal
        # lands here) over the generic operation-level sentence, and never hand
        # back a blank -- a blank is indistinguishable from a timeout.
        text = " | ".join(notes) or (result.get("message") or "").strip()
        if not text:
            text = json.dumps(result, ensure_ascii=False)
        print(f"!! Empty response from Tyr -- reporting runtime detail instead: {text[:200]}")
    elif notes:
        # A reply came back AND something underneath it failed. Keep both: the
        # reply may be a partial answer whose gap the notes explain.
        text = f"{text}\n[runtime detail] " + " | ".join(notes)

    return TyrReply(text, op_id, result.get("state", "unknown"), outcome, result, notes)


def confirm_actions_enabled() -> None:
    """Actions can create/delete real agents and have them touch a real
    filesystem. Require an explicit typed confirmation, in addition to the
    per-action approval gate, before running with ALLOW_ACTIONS on."""
    print(
        "\n!! ALLOW_ACTIONS is on: this run can create/delete agents and hand "
        "them real instructions (still gated by per-action approval below)."
    )
    if input("Type 'yes' to continue: ").strip().lower() != "yes":
        sys.exit("Aborted.")


def render_transcript(loop_messages: list[dict]) -> str:
    return "\n\n".join(f"[{m['role'].upper()}] {m['content']}" for m in loop_messages[1:])


def dedupe_transcript(messages: list[dict]) -> list[dict]:
    """Replace a message that repeats one already kept with a short stub.

    A stuck case repeats the SAME reply verbatim many times (78 identical
    workspace-topology dumps in one observed run); those add length without
    adding anything the report needs. Comparison is on normalized text, so
    cosmetic differences still collapse; only bulky messages (>200 chars) are
    eligible, so short instructions stay intact. The first occurrence is always
    kept in full -- only later duplicates become stubs."""
    seen: set[str] = set()
    out: list[dict] = []
    for m in messages:
        norm = normalize_message(m["content"])
        if len(m["content"]) > 200 and norm in seen:
            stub = ("[identical to an earlier Tyr reply above -- omitted to save context]"
                    if m["role"] == "user"
                    else "[identical to an earlier message above -- omitted]")
            out.append({"role": m["role"], "content": stub})
        else:
            seen.add(norm)
            out.append(m)
    return out


def clip_middle(text: str, max_chars: int) -> str:
    """Trim `text` to `max_chars` by cutting the MIDDLE, keeping head and tail.

    A QA report needs both a case's setup (head) and its outcome (tail), so a
    plain truncation from either end would drop half of what matters. The elision
    marker records how much was removed."""
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - 120)
    head = keep // 3
    tail = keep - head
    elided = len(text) - keep
    return (
        text[:head]
        + f"\n\n[... {elided} characters of transcript elided to fit the model context window ...]\n\n"
        + text[len(text) - tail:]
    )


def fit_transcript(loop_messages: list[dict], overhead_chars: int, out_tokens: int) -> str:
    """A transcript, deduped and clipped so input + output stay under the window.

    `overhead_chars` is the length of the surrounding prompt with an empty
    transcript -- the template and whatever case text goes with it. Whatever
    token budget is left after that and the output allowance, converted to
    chars, is the transcript's."""
    transcript = render_transcript(dedupe_transcript(loop_messages))
    budget_chars = (CONTEXT_TOKEN_LIMIT - out_tokens) * CHARS_PER_TOKEN - overhead_chars
    budget_chars = max(2000, budget_chars)
    if len(transcript) > budget_chars:
        print(f"!! Transcript is {len(transcript)} chars (budget {budget_chars}) -- "
              f"clipping to fit the {CONTEXT_TOKEN_LIMIT}-token context window.")
        transcript = clip_middle(transcript, budget_chars)
    return transcript




# ─────────────────────────────────────────────────────────────
# STUCK DETECTION
# ─────────────────────────────────────────────────────────────
#
# Observed failure: the Loop Agent asks a compound question, Tyr answers with a
# non-answer ("Found 2 Workspace Bridges."), and the Loop Agent spends the rest
# of the phase re-asking the SAME question in slightly different words -- each
# turn perfectly reasonable read in isolation, which is exactly why the model
# never notices. Nothing in the transcript says "you are looping", so the
# harness has to say it, and escalate what it demands each time.
#
# Two signals count as looping, either one is enough:
#   - Tyr's reply is (near) identical to its previous one -- the rewording
#     changed nothing on the receiving end.
#   - our own message is (near) identical to the one before it -- a paraphrase
#     loop, even if Tyr's replies happen to differ.

# Ratio above which two normalized messages count as "the same thing said
# twice". 0.85 catches the observed rewordings ("which are the peer workspace
# names..." vs "which peer workspace names do those Bridges connect to...")
# while leaving room for a genuinely narrowed follow-up to read as new.
STUCK_SIMILARITY = 0.85

# Tyr sometimes fails a request in a way that is explicitly NOT final: the
# request never landed and it says so ("I couldn't complete that request
# automatically. Please try again."). Observed in real runs, where the Loop
# Agent read it as a verdict and ended the case -- but nothing was tested, so
# it is neither PASS nor FAIL. The stuck detector cannot catch this: it needs a
# repetition, and a single retry invitation is not one.
#
# This is the one situation where re-sending the IDENTICAL request is correct,
# which is exactly what the anti-paraphrase nudges punish -- hence the two are
# kept mutually exclusive below.
RETRYABLE_REPLY_RE = re.compile(
    r"couldn'?t complete .{0,40}automatic"
    r"|could not complete .{0,40}automatic"
    r"|please try again"
    r"|try (?:that |this |again)"
    r"|temporarily unavailable"
    r"|something went wrong"
    r"|no response (?:was )?received",
    re.I,
)

# How many straight resends to sanction before calling it an observed defect.
RETRY_LIMIT = 2

RETRY_EXHAUSTED_NUDGE = (
    "[HARNESS: this request has now failed transiently {n} times in a row. Stop "
    "retrying it. Record 'the request repeatedly failed to go through -- "
    "<quote the exact wording Tyr returned>' as the observed outcome for this "
    "step and move on. A repeated transient failure IS a reportable finding.]"
)

STUCK_NUDGES = (
    "[HARNESS: that is the SAME reply as last turn -- your rewording changed "
    "nothing. Stop paraphrasing. Change the shape of the request: ask about "
    "exactly ONE named item, ask for ONE field, or state the exact format you "
    "want back. Another differently-worded version of the same question will "
    "return this same reply.]",

    "[HARNESS: same reply a THIRD time. Rephrasing is not going to work. This "
    "turn must be structurally different: split the question into its smallest "
    "part and ask only that; or name a single item and ask for its full record; "
    "or ask outright whether that detail is available to you at all and why it "
    "is not being returned. An explicit 'I can't' is a usable result.]",

    "[HARNESS: this line of questioning is exhausted -- do NOT ask it again in "
    "any wording. Either proceed with what you already have, try a completely "
    "different route (another agent, another workspace, another angle), or "
    "record what you observed as the outcome and emit your stop token.]",
)


def find_stop_token(message: str, stop_prefixes: tuple[str, ...]) -> str | None:
    """The control token in `message`, or None.

    Matches ANYWHERE in the message, not just at the start. Models routinely
    narrate before signalling ("Record the observed outcome as a failure...
    <<DONE>>"), and an anchored check misses that -- the message then falls
    through to send_to_tyr() and hands the Agent under test both the harness's
    control token and the tester's private reasoning."""
    return next((p for p in stop_prefixes if p in message), None)


def normalize_message(text: str) -> str:
    """Collapse to comparable form -- case, punctuation, and whitespace differences
    are exactly what a paraphrase loop varies, so none of them should count."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def is_repeat(current: str, previous: str | None) -> bool:
    """True when `current` says the same thing as `previous`."""
    if not previous:
        return False
    a, b = normalize_message(current), normalize_message(previous)
    if not a or not b:
        return False
    return a == b or SequenceMatcher(None, a, b).ratio() >= STUCK_SIMILARITY


def retry_nudge(attempt: int) -> str:
    """Told to the Loop Agent when a request failed transiently, not finally."""
    return (
        f"[HARNESS: that reply says the request did not go through -- it was not "
        f"refused, and nothing was tested, so this is not an outcome. Send the "
        f"SAME request again, unchanged; the no-paraphrasing rule does not apply "
        f"to a transient failure. Attempt {attempt} of {RETRY_LIMIT}.]"
    )


def stuck_nudge(streak: int) -> str:
    """The escalation rung for `streak` consecutive no-progress turns ("" for 0).
    Streaks past the last rung keep getting it -- the last rung says "stop"."""
    if streak < 1:
        return ""
    return STUCK_NUDGES[min(streak, len(STUCK_NUDGES)) - 1]


# ─────────────────────────────────────────────────────────────
# CONVERSATION LOOP
# ─────────────────────────────────────────────────────────────


def converse(
    brain: "LoopAgentClient",
    tyr: TyrMCPClient,
    system_prompt: str,
    loop_messages: list[dict],
    tyr_operation_id: str | None,
    max_turns: int,
    phase: str,
    stop_prefixes: tuple[str, ...] = (STOP_TOKEN,),
    runtime_vars: tuple[str, ...] = (),
) -> tuple[list[dict], str | None]:
    """Run up to max_turns of Loop Agent <-> Tyr exchange, mutating and
    returning loop_messages/tyr_operation_id.

    Stops early when the Loop Agent emits any of stop_prefixes. Those are
    harness control tokens, so the message is recorded in loop_messages (the
    discovery phase parses its result back out of the transcript) but is NEVER
    sent to Tyr -- transmitting one would leak the harness's own signalling to
    the Agent under test."""
    # Loop detection state: the previous exchange, and how many turns in a row
    # have made no progress. See stuck_nudge().
    last_sent: str | None = None
    last_reply: str | None = None
    stuck_streak = 0
    # Consecutive transient failures on the current request. See retry_nudge().
    retry_streak = 0

    for turn in range(1, max_turns + 1):
        print(f"\n=== [{phase}] Turn {turn}/{max_turns} ===")

        try:
            next_message = call_model(brain, loop_messages, max_tokens=TURN_MAX_TOKENS, system=system_prompt)
        except LoopAgentBlocked as blocked:
            # The QA tester itself was stopped, so this turn never reached Tyr.
            # Never let it pass as a normal end-of-phase: report the provider's
            # exact reason on the terminal and keep it in the log.
            print(f"\n!! LOOP AGENT BLOCKED on [{phase}] turn {turn} -- the tester's own model "
                  f"produced no message, so nothing was sent to Tyr.")
            print(f"!! Reason: {blocked.reason}")
            if blocked.detail:
                print(f"!! Provider detail: {json.dumps(blocked.detail, ensure_ascii=False)[:600]}")
            print("!! Stopping this phase early -- do not read it as a completed phase.")
            log({
                "phase": phase,
                "turn": turn,
                "loopAgentBlocked": blocked.reason,
                "loopAgentBlockDetail": blocked.detail,
                "sentToTyr": False,
            })
            break

        stop_token = find_stop_token(next_message, stop_prefixes)
        if stop_token:
            print(f"Loop Agent signaled stop ({stop_token}): {next_message[:120]}")
            # Recorded in full -- parse_discovery_options() reads its result back
            # out of the transcript -- but never sent.
            loop_messages.append({"role": "assistant", "content": next_message})
            log({"phase": phase, "turn": turn, "stopToken": next_message, "sentToTyr": False})
            break

        # A case's ALL_CAPS variables are the Loop Agent's own notepad. Sending
        # the name instead of the recorded value produces a message nobody on
        # the other side can act on ("move it and update VISUALIZATION_FULL_PATH"),
        # and the reply that comes back looks like a refusal rather than a
        # malformed request. Correct it here instead of spending the turn.
        leaked = [var for var in runtime_vars if var in next_message]
        if leaked:
            print(f"!! Loop Agent sent bookkeeping variable(s) {', '.join(leaked)} verbatim -- "
                  f"not forwarding; asking it to substitute the recorded value.")
            log({"phase": phase, "turn": turn, "leakedRuntimeVars": leaked,
                 "draft": next_message, "sentToTyr": False})
            loop_messages.append({"role": "assistant", "content": next_message})
            loop_messages.append({"role": "user", "content": (
                f"[HARNESS: not sent. {', '.join(leaked)} is your own note-keeping name -- "
                f"the recipient has never heard of it. Re-send this message with the actual "
                f"value you recorded substituted in. If you have not been told that value "
                f"yet, ask for it plainly instead, and drop any 'record/update ...' wording: "
                f"that part is an instruction to you, not to them.]"
            )})
            continue

        print(f"Loop Agent -> Tyr: {next_message}")
        loop_messages.append({"role": "assistant", "content": next_message})

        try:
            reply = send_to_tyr(tyr, next_message, tyr_operation_id)
            tyr_operation_id = reply.operation_id
        except TyrMCPError as e:
            reply = TyrReply(f"ERROR calling Tyr: {e}", tyr_operation_id, "error", "settled", {})

        # Tell the Loop Agent exactly how much to trust this reply -- each
        # outcome calls for a different next move from it.
        if reply.outcome == "our_turn":
            label = (
                f"[Tyr Assistant is waiting on more input from you "
                f"(state={reply.state!r}) -- answer its question to continue]"
            )
            print(f"!! Tyr needs input (state={reply.state!r}) -- handing back to the Loop Agent.")
        elif reply.outcome == "timeout":
            label = (
                f"[Tyr Assistant has NOT finished yet -- gave up polling after "
                f"{POLL_MAX_ATTEMPTS} attempts, last known state={reply.state!r}. "
                f"This may be stale/incomplete -- check again before treating it "
                f"as final]"
            )
            print(f"!! Not settled (state={reply.state!r}) -- flagging as provisional.")
        else:
            label = "[Tyr Assistant replied]"

        # Transient failure takes priority over the stuck check. Resending the
        # identical request is the RIGHT move here, and that is precisely what
        # the anti-paraphrase nudge punishes -- so the two must never fire on
        # the same turn.
        if reply.outcome == "settled" and RETRYABLE_REPLY_RE.search(reply.text):
            retry_streak += 1
            if retry_streak <= RETRY_LIMIT:
                label = f"{label} {retry_nudge(retry_streak)}"
                stuck_streak = 0  # an intentional resend is not being stuck
                print(f"!! Transient failure from Tyr ({retry_streak}/{RETRY_LIMIT}) -- "
                      f"asking the Loop Agent to resend the same request.")
            else:
                label = f"{label} {RETRY_EXHAUSTED_NUDGE.format(n=retry_streak)}"
                print(f"!! Transient failure x{retry_streak} -- telling the Loop Agent to "
                      f"stop retrying and record it as a finding.")
        else:
            retry_streak = 0
            # No progress this turn if we said the same thing again, or Tyr did.
            # Either way the next turn needs a different move, not another rewrite.
            if is_repeat(next_message, last_sent) or is_repeat(reply.text, last_reply):
                stuck_streak += 1
                label = f"{label} {stuck_nudge(stuck_streak)}"
                print(f"!! Stuck: {stuck_streak} turn(s) with no progress -- nudging the Loop Agent.")
            else:
                stuck_streak = 0

        last_sent, last_reply = next_message, reply.text

        print(f"Tyr -> Loop Agent: {reply.text[:400]}{'...' if len(reply.text) > 400 else ''}")
        loop_messages.append({"role": "user", "content": f"{label}: {reply.text}"})

        log({
            "phase": phase,
            "turn": turn,
            "stuckStreak": stuck_streak,
            "retryStreak": retry_streak,
            "operationId": tyr_operation_id,
            "to_tyr": next_message,
            "from_tyr": reply.text,
            "tyrState": reply.state,
            "outcome": reply.outcome,
            "settled": reply.outcome == "settled",  # kept for older log readers
            # Why a runtime/bridge didn't succeed -- a safety refusal shows up
            # here. Empty on clean turns; grep the log for it to find refusals.
            "notes": list(reply.notes),
            # Payload minus the reply text (already above as from_tyr): the only
            # way to learn the shape of executions[] / bridges[] from real
            # delegating turns, which the tool schema doesn't pin down. Logs are
            # gitignored run artifacts.
            "raw": loggable_raw(reply.raw),
        })

        print("-" * 60)

    return loop_messages, tyr_operation_id


# ─────────────────────────────────────────────────────────────
# PHASES
# ─────────────────────────────────────────────────────────────


def parse_discovery_options(transcript: str) -> list[dict]:
    """Pull the file locations the discovery phase found out of its transcript.

    The Loop Agent ends discovery with a stop token of the form
      <<DISCOVERY_COMPLETE: PATH:/p|WORKSPACE:w|AGENT:a>>
    Returns one dict per option with PATH/WORKSPACE/AGENT keys, or an empty
    list if discovery failed or its output couldn't be parsed.

    The whitespace after the colon is optional and the match is non-greedy: the
    prompt shows one space, but converse() stops the phase on the token PREFIX
    alone, so a model that omitted the space used to stop discovery and then
    fail to parse -- which reads as "no location found" and exits the run. A
    greedy `.+` had the matching problem from the other end, running one token
    into a later one and parsing neither."""
    match = re.search(r"<<DISCOVERY_COMPLETE:\s*(.+?)>>", transcript, re.S)
    if not match:
        return []

    options = []
    for chunk in match.group(1).split(";"):
        # Tolerate a leading "OPTION_1:" label. An earlier prompt asked for one,
        # and it silently broke every option: the split below would read the
        # label as the key and swallow PATH into its value, so nothing parsed.
        chunk = re.sub(r"^\s*OPTION_\d+\s*:\s*", "", chunk.strip(), flags=re.I)

        fields = {}
        for part in chunk.split("|"):
            if ":" in part:
                key, value = part.split(":", 1)
                fields[key.strip().upper()] = value.strip()
        if {"PATH", "WORKSPACE", "AGENT"} <= fields.keys():
            options.append(fields)
    return options


def run_discovery(
    brain: "LoopAgentClient",
    tyr: TyrMCPClient,
    tyr_operation_id: str | None,
    report_file: str | None = None,
) -> tuple[dict, str | None]:
    """Phase 1. Returns the target to test against (PATH/WORKSPACE/AGENT).
    Exits the process if no usable location was found -- every test case
    depends on having one.

    The prompt asks for ONE confirmed location. It used to ask for two or three
    so a stalled case could fall back to another agent, but nothing ever read
    past the first, so the extra Bridges were explored at the cost of real
    discovery turns. Several are still parsed and reported if a run produces
    them; only the first is used."""
    messages, tyr_operation_id = converse(
        brain, tyr, render_discovery_prompt(),
        [{"role": "user", "content": "Begin discovery."}],
        tyr_operation_id, EXPLORE_TURNS, phase="discovery",
        stop_prefixes=(DISCOVERY_DONE_PREFIX, DISCOVERY_FAILED_TOKEN),
    )

    options = parse_discovery_options(render_transcript(messages))

    # The target file is under /home by definition. Enforce that here rather
    # than trusting the prompt: a peer Agent reporting /root/important.txt is
    # reporting a different file, and running the whole plan against it would
    # produce confident, wrong results.
    in_scope = [o for o in options if o["PATH"].startswith(SEARCH_ROOT + "/")]
    for rejected in [o for o in options if o not in in_scope]:
        print(f"  ! Ignoring out-of-scope hit (not under {SEARCH_ROOT}): {rejected['PATH']}")
    options = in_scope

    if not options:
        # Stop the run here. Nothing further is sent to Tyr: the execute phase
        # never starts, and the failure token itself was never transmitted.
        print(f"✗ Discovery failed -- no usable file location found under {SEARCH_ROOT}.")
        log({"phase": "discovery", "discoveryFailed": True, "parsedOptions": 0})
        report_file = save_report(
            "# Discovery failed\n\n"
            f"No usable location for `important.txt` was confirmed under `{SEARCH_ROOT}`, so no "
            "test case ran and there is nothing to grade.\n\n"
            "Either the discovery phase emitted `<<DISCOVERY_FAILED>>`, or it ran out of turns, or "
            "every location it reported was outside the search root.\n\n"
            f"**Run id:** `{RUN_ID}` -- grep `\"runId\": \"{RUN_ID}\"` in `{LOG_FILE}` for the "
            "turn-by-turn discovery transcript.\n\n"
            "Nothing further was sent to Tyr.\n",
            report_file,
        )
        sys.exit(f"Cannot proceed without a confirmed file path. Wrote {report_file}.")

    print(f"✓ Discovery confirmed {len(options)} location(s):")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. Path: {opt['PATH']}")
        print(f"     Workspace: {opt['WORKSPACE']}")
        print(f"     Agent: {opt['AGENT']}")
    if len(options) > 1:
        print("\nTesting against the first; the rest are recorded but unused.")

    return options[0], tyr_operation_id


def run_test_cases(
    brain: "LoopAgentClient",
    tyr: TyrMCPClient,
    test_plan: list[dict],
    target: dict,
    tyr_operation_id: str | None,
    report_file: str,
) -> tuple[list[str], str | None]:
    """Phase 2. Run each case in its own conversation, seeded with the target
    discovery confirmed, grade it the moment it finishes, and return the
    finished report sections.

    Each case is graded and written to `report_file` before the next one starts.
    That ordering is the point: whatever goes wrong later -- a case that
    overflows the context, a provider block, a Ctrl-C -- the cases already
    finished are on disk as findings, not as raw transcript nobody turned into
    a result.

    Case ids and titles are printed to the console and used in the report, but
    are deliberately kept out of everything the Loop Agent sees -- it relays its
    context into live messages, so harness labelling there could reach the Agent
    under test."""
    print(f"\nRunning {len(test_plan)} test case(s):")
    for case in test_plan:
        print(f"  - [{case['id']}] {case['title']} ({case.get('category', '?')})")

    sections: list[str] = []

    for i, case in enumerate(test_plan, start=1):
        print(f"\n--- Test case {i}/{len(test_plan)}: {case['id']} ---")
        context = (
            f"File location confirmed: PATH={target['PATH']} "
            f"WORKSPACE={target['WORKSPACE']} AGENT={target['AGENT']}. "
            f"Begin."
        )
        messages, tyr_operation_id = converse(
            brain, tyr, render_execute_prompt(case, target, STOP_TOKEN),
            [{"role": "user", "content": context}],
            tyr_operation_id, MAX_TURNS, phase=f"execute-case-{i}",
            runtime_vars=runtime_variables(case),
        )
        print(f"✓ Case {i} ran: {case['id']} -- grading it now")

        sections.append(grade_case(brain, case, messages, target))
        save_report(assemble_report(test_plan, sections, target=target), report_file)
        print(f"✓ Case {i} graded: {result_of(sections[-1]) or 'unparsed'} -> {report_file}")

    return sections, tyr_operation_id


def next_report_path() -> str:
    """The next free <REPORT_PREFIX>_<n>.md, numbered past any earlier run.

    Allocated ONCE per run and then rewritten in place as each case is graded,
    so an interrupted run leaves one file holding everything finished so far --
    not one file per case, and not nothing at all."""
    nums = []
    for name in os.listdir("."):
        if name.startswith(REPORT_PREFIX + "_") and name.endswith(".md"):
            try:
                nums.append(int(name[len(REPORT_PREFIX) + 1:-3]))
            except ValueError:
                pass
    return f"{REPORT_PREFIX}_{max(nums, default=0) + 1}.md"


def save_report(report: str, report_file: str | None = None) -> str:
    """Write `report`, to `report_file` if given or a freshly numbered one.

    Every way a run can end goes through here, including the ones that end
    early: a run that produces no file at all leaves the operator with nothing
    to read but a multi-MB log."""
    report_file = report_file or next_report_path()
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    return report_file


# ─────────────────────────────────────────────────────────────
# REPORTING -- graded per case, as each one finishes
# ─────────────────────────────────────────────────────────────
#
# Observed failure: a run completed cases 1, 2 and 3, then case 4 spiralled to
# 52 turns and overflowed the context window. The report was a single model call
# over the whole run's transcript, so it overflowed too -- and the finished
# write-ups for the three cases that HAD passed were never produced. The evidence
# existed; nothing had been asked to turn it into findings yet.
#
# So each case is graded the moment it finishes, from its own transcript, and the
# report file is rewritten after every case. A later failure can now cost at most
# the case it actually hit.

RESULT_MARKERS = ("✅ PASS", "❌ FAIL", "⚠️ PARTIAL", "⏭️ NOT ATTEMPTED", "🚧 NOT GRADED")


def result_of(section: str) -> str | None:
    """The verdict a finished subsection carries, read back off its Result line."""
    for marker in RESULT_MARKERS:
        if re.search(r"\*\*Result:\*\*\s*" + re.escape(marker), section):
            return marker
    return None


def tally_line(sections: list[str]) -> str:
    """Status tally, counted from the sections rather than asked of the model.

    The grader was previously asked to total its own verdicts, which is both
    avoidable arithmetic and unverifiable. Counting here also means the tally
    stays right on a partial report."""
    counts = {marker: 0 for marker in RESULT_MARKERS}
    for section in sections:
        marker = result_of(section)
        if marker:
            counts[marker] += 1
    shown = [f"{m.split()[0]} {n}" for m, n in counts.items() if n or m != "🚧 NOT GRADED"]
    return "  ".join(shown)


def grade_case(
    brain: "LoopAgentClient",
    case: dict,
    messages: list[dict],
    target: dict | None,
) -> str:
    """One case's finished report subsection, from that case's transcript alone.

    Never raises: if the grading call is blocked, the case still gets a
    subsection saying so. A case that ran deserves a line in the report whether
    or not a model was available to write it up."""
    overhead = len(render_case_report_prompt(case, "", target))
    transcript = fit_transcript(messages, overhead, SECTION_MAX_TOKENS)
    try:
        section = call_model(
            brain,
            [{"role": "user",
              "content": render_case_report_prompt(case, transcript, target)}],
            max_tokens=SECTION_MAX_TOKENS,
        )
    except LoopAgentBlocked as blocked:
        print(f"!! Could not grade [{case['id']}]: {blocked.reason}")
        log({"phase": "report-case", "caseId": case["id"],
             "loopAgentBlocked": blocked.reason, "loopAgentBlockDetail": blocked.detail})
        return "\n".join([
            case_heading(fill_target(case, target) if target else case),
            "",
            "**Result:** 🚧 NOT GRADED",
            f"**What happened:** the case ran, but writing up its findings failed -- {blocked.reason}",
            f"**Evidence:** the turn-by-turn transcript is in `{LOG_FILE}` "
            f"under runId `{RUN_ID}`.",
        ])

    log({"phase": "report-case", "caseId": case["id"], "result": result_of(section)})
    return section.strip()


def assemble_report(
    test_plan: list[dict],
    sections: list[str],
    summary: str | None = None,
    target: dict | None = None,
) -> str:
    """The report file: header, tally, every case's subsection, then the summary.

    Cases with no section yet are listed as ⏭️ NOT ATTEMPTED, so a report
    written mid-run still accounts for the whole plan rather than trailing off."""
    graded = len(sections)
    pending = []
    for case in test_plan[graded:]:
        pending.append("\n".join([
            case_heading(fill_target(case, target) if target else case),
            "",
            "**Result:** ⏭️ NOT ATTEMPTED",
            "**Reason:** the run ended before this case started.",
        ]))

    parts = [
        "# Tyr Assistant QATestSearch Report",
        "",
        "`Legend: ✅ PASS · ❌ FAIL · ⚠️ PARTIAL · ⏭️ NOT ATTEMPTED · 🚧 NOT GRADED`",
        "",
        f"`Run: {RUN_ID}` · `Model: {MODEL}` · `Cases graded: {graded}/{len(test_plan)}`",
        "",
        f"Status tally: `{tally_line(sections + pending)}`",
    ]
    if summary is None and pending:
        parts += ["", "> **This run did not finish.** Everything below was graded as it "
                  "completed; the remaining cases never ran."]
    if summary:
        parts += ["", summary.strip()]
    parts += ["", "## Findings", ""]
    parts.append("\n\n".join(sections + pending))
    return "\n".join(parts).rstrip() + "\n"


def write_report(
    brain: "LoopAgentClient",
    test_plan: list[dict],
    sections: list[str],
    target: dict | None = None,
    report_file: str | None = None,
) -> str:
    """Phase 3. Finish the report the execute phase has been writing all along.

    Every case was already graded and saved as it completed, so this adds only
    the two things that need the whole run in view: the delivery paragraph and
    the issues list. It runs over the finished SECTIONS, never the transcripts,
    so it stays small -- and if it is blocked anyway, the per-case findings are
    already on disk and the report is written without it."""
    summary = None
    if sections:
        try:
            summary = call_model(
                brain,
                [{"role": "user", "content": render_summary_prompt("\n\n".join(sections))}],
                max_tokens=SECTION_MAX_TOKENS,
            )
        except LoopAgentBlocked as blocked:
            # Costs the summary paragraph and the issues list. Every case's
            # findings survive -- that is the whole point of grading per case.
            print(f"\n!! Summary generation blocked -- per-case findings are unaffected.")
            print(f"!! Reason: {blocked.reason}")
            log({"phase": "report-summary", "loopAgentBlocked": blocked.reason,
                 "loopAgentBlockDetail": blocked.detail})
            summary = (
                "## Issues needing attention\n\n"
                f"_The run-level summary could not be generated ({blocked.reason}). "
                "The per-case findings below are unaffected; read them directly._"
            )

    return save_report(
        assemble_report(test_plan, sections, summary=summary, target=target), report_file
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────


def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("Set OPENROUTER_API_KEY before running.")

    print(f"Python: {sys.executable}")
    print(f"Run id: {RUN_ID}")
    print(f"Loop Agent model: {MODEL} (via OpenRouter: {OPENROUTER_BASE_URL})")
    print(f"Mode: {'ACTIONS ALLOWED (tyr_assistant_request)' if ALLOW_ACTIONS else 'READ-ONLY (tyr_assistant_query)'}")
    if ALLOW_ACTIONS:
        confirm_actions_enabled()

    # First line of the run. Every setting that changes how a run behaves is
    # recorded here, so a log read months later says which model produced it and
    # under which budgets -- none of which was recoverable from the turns alone.
    log({
        "phase": "run-start",
        "model": MODEL,
        "allowActions": ALLOW_ACTIONS,
        "exploreTurns": EXPLORE_TURNS,
        "maxTurns": MAX_TURNS,
        "turnMaxTokens": TURN_MAX_TOKENS,
        "contextTokenLimit": CONTEXT_TOKEN_LIMIT,
        "searchRoot": SEARCH_ROOT,
        "cases": [case["id"] for case in TEST_CASES],
    })

    try:
        tyr = TyrMCPClient()
        tyr.initialize()
    except TyrMCPError as e:
        sys.exit(str(e))

    brain = LoopAgentClient(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        default_headers={"X-Title": "Tyr Loop Agent"},  # optional OpenRouter attribution
    )

    # Named up front so every phase writes into the SAME file. The report is
    # built up as the run goes rather than produced at the end.
    report_file = next_report_path()
    print(f"Report -> {report_file} (rewritten after each case)")

    # Phase 1: find the file. Exits if it can't -- the cases all need a target.
    print("\n### Phase 1/3: Discover file location ###")
    target, tyr_operation_id = run_discovery(brain, tyr, None, report_file)

    # Phase 2: run every case against that target, one case per conversation,
    # grading and saving each one before the next starts.
    print("\n### Phase 2/3: Execute test plan ###")
    sections, _ = run_test_cases(
        brain, tyr, TEST_CASES, target, tyr_operation_id, report_file
    )

    # Phase 3: add only what needs the whole run in view -- delivery summary
    # and issues list. The findings themselves are already written.
    print("\n### Phase 3/3: Summarize ###")
    write_report(brain, TEST_CASES, sections, target, report_file)

    print(f"Done. Log -> {LOG_FILE} | Report -> {report_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
