#!/usr/bin/env python3
"""
Loop Agent <-> Tyr Assistant

Runs a small LLM ("Loop Agent") as a functional QA tester of Tyr Assistant,
in four phases:
  1. Explore Tyr for a few turns to map its real capabilities -- connected
     agents, device actions, file/image operations, web browsing, multi-agent
     workflows, and channel behavior.
  2. Design its own test plan from what it learned (prompt_qa.SEED_TEST_IDEAS
     is inspiration only, not a script).
  3. Execute that self-authored plan against Tyr, turn by turn.
  4. Write a Markdown QA report with emoji status markers.

The Loop Agent's own model calls go through OpenRouter's OpenAI-compatible
API, so you can drive it with any Claude model your OpenRouter account can
reach (e.g. anthropic/claude-sonnet-5). Tyr Assistant itself is still reached
over its own MCP server (see mcp_client.py) -- that connection is unchanged.

Required env vars:
  TYR_MCP_TOKEN       Tyr bearer token (see mcp_client.py for how to get one)
  OPENROUTER_API_KEY  OpenRouter API key for the Loop Agent's own model calls

Optional env vars:
  TYR_LOOP_MODE            "qa" (default), "redteam", or "filehunt" -- picks
                           which prompt module drives the run. "qa" is
                           the general functional QA suite (prompt_qa.py).
                           "redteam" is adversarial security testing
                           (prompts_redteam.py); it skips exploration.
                           "filehunt" runs a fixed two-scenario suite against
                           a specific file, important.txt
                           (prompts_filehunt.py): it explores to locate the
                           file, then executes the two scenarios directly --
                           there is no planning phase.
  TYR_LOOP_ALLOW_ACTIONS   "true" to allow mutating tyr_assistant_request
                           calls (needed for most non-trivial test cases).
                           Default: read-only.
  TYR_LOOP_EXPLORE_TURNS   Turns budgeted for phase 1. Default: 5.
  TYR_LOOP_MAX_TURNS       Turns budgeted for phase 3. Default: 150.
  TYR_LOOP_MODEL           OpenRouter model slug for the Loop Agent's own
                           calls. Default: anthropic/claude-sonnet-5.
  OPENROUTER_BASE_URL      Override the OpenRouter API base URL.

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
import sys
from datetime import datetime, timezone

try:
    from openai import OpenAI
except ImportError as e:
    sys.exit(
        f"Missing dependency ({e}). Install into THIS interpreter with:\n"
        f"  {sys.executable} -m pip install -r requirements.txt"
    )

import importlib

from mcp_client import TyrMCPClient, TyrMCPError

_MODE = os.environ.get("TYR_LOOP_MODE", "qa").lower()
_MODULE_BY_MODE = {"qa": "prompt_qa", "redteam": "prompts_redteam", "filehunt": "prompts_filehunt"}
_prompts = importlib.import_module(_MODULE_BY_MODE.get(_MODE, "prompt_qa"))
SEED_TEST_IDEAS = _prompts.SEED_TEST_IDEAS
render_execute_prompt = _prompts.render_execute_prompt
render_explore_prompt = _prompts.render_explore_prompt
render_plan_prompt = getattr(_prompts, "render_plan_prompt", None)
render_report_prompt = _prompts.render_report_prompt
ensure_mandatory_cases = getattr(_prompts, "ensure_mandatory_cases", lambda plan: plan)
SKIP_PLAN_PHASE = getattr(_prompts, "SKIP_PLAN_PHASE", False)

# ─────────────────────────────────────────────────────────────
# CONFIG -- edit before running, or override via env vars
# ─────────────────────────────────────────────────────────────

STOP_TOKEN = "<<DONE>>"
# Explore: enough turns to map agents/devices/channels before planning.
# Execute: red-team runs 30 cases with a first-pass cap of 2-3 turns each
# (60-90 turns) plus follow-up on promising leads; QA runs ~50 cases with
# multi-turn verification. 400 turns comfortably covers both.
_DEFAULT_EXPLORE_TURNS = {"redteam": "0", "filehunt": "8"}.get(_MODE, "5")
# (filehunt explores to locate important.txt before executing its two fixed scenarios.)
EXPLORE_TURNS = int(os.environ.get("TYR_LOOP_EXPLORE_TURNS", _DEFAULT_EXPLORE_TURNS))
MAX_TURNS = int(os.environ.get("TYR_LOOP_MAX_TURNS", "400"))
# OpenRouter model slug for the Loop Agent's brain. Any Claude model your
# OpenRouter account can reach works -- e.g. anthropic/claude-opus-4.8,
# anthropic/claude-fable-5. See https://openrouter.ai/models for the full list.
MODEL = os.environ.get("TYR_LOOP_MODEL", "anthropic/claude-opus-4.8")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Safety: when False (default) the Loop Agent can only ask read-only questions
# (tyr_assistant_query). Most non-trivial test cases it designs for itself
# need this True to run at all -- tyr_assistant_request can hand real
# instructions to a dev-full-access Agent running on a real machine. Every
# individual action still needs a human approval (see resolve_pending_approvals
# below) before it actually executes.
ALLOW_ACTIONS = os.environ.get("TYR_LOOP_ALLOW_ACTIONS", "false").lower() == "true"

# How long to long-poll a not-yet-finished operation before giving up on it.
POLL_WAIT_SECONDS = 30
POLL_MAX_ATTEMPTS = 10

LOG_FILE = f"tyr_{_MODE}_log.jsonl"
_REPORT_PREFIX_BY_MODE = {"qa": "tester", "redteam": "red_teamer", "filehunt": "file_hunter"}
_REPORT_PREFIX = _REPORT_PREFIX_BY_MODE.get(_MODE, "tester")

TERMINAL_STATES = {"completed", "failed", "error", "cancelled", "rejected"}

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────


def log(entry: dict) -> None:
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def divider() -> None:
    print("-" * 60)


def call_model(
    brain: "OpenAI",
    messages: list[dict],
    max_tokens: int,
    system: str | None = None,
) -> str:
    """One Loop Agent model call via OpenRouter's OpenAI-compatible chat API.
    Prepends `system` as a system message when given, and returns the reply
    text (empty string if the model returned no content)."""
    if system is not None:
        messages = [{"role": "system", "content": system}, *messages]
    completion = brain.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=messages,
    )
    return (completion.choices[0].message.content or "").strip()


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


def send_to_tyr(
    tyr: TyrMCPClient, message: str, operation_id: str | None
) -> tuple[str, str | None, str]:
    """Send one message to Tyr, poll until it settles, return (reply_text,
    operation_id, state). state is whatever Tyr's last-known state was --
    check it against TERMINAL_STATES to know whether this is a real final
    answer or we just ran out of polling attempts while it was still
    running/pending."""
    send = tyr.request if ALLOW_ACTIONS else tyr.query
    result = send(message, operation_id=operation_id)

    op_id = result.get("operationId", operation_id)
    attempts = 0
    while result.get("state") not in TERMINAL_STATES and attempts < POLL_MAX_ATTEMPTS:
        approvals = result.get("pendingApprovals") or []
        if approvals and op_id:
            resolve_pending_approvals(tyr, op_id, approvals)
        result = tyr.operation_status(op_id, wait_seconds=POLL_WAIT_SECONDS)
        attempts += 1

    reply = result.get("response") or result.get("message") or json.dumps(result)
    return reply, op_id, result.get("state", "unknown")


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


# ─────────────────────────────────────────────────────────────
# PHASES
# ─────────────────────────────────────────────────────────────


def converse(
    brain: "OpenAI",
    tyr: TyrMCPClient,
    system_prompt: str,
    loop_messages: list[dict],
    tyr_operation_id: str | None,
    max_turns: int,
    phase: str,
) -> tuple[list[dict], str | None]:
    """Run up to max_turns of Loop Agent <-> Tyr exchange, mutating and
    returning loop_messages/tyr_operation_id. Stops early on STOP_TOKEN."""
    for turn in range(1, max_turns + 1):
        print(f"\n=== [{phase}] Turn {turn}/{max_turns} ===")

        next_message = call_model(brain, loop_messages, max_tokens=1024, system=system_prompt)

        if next_message == STOP_TOKEN or not next_message:
            print("Loop Agent signaled done.")
            break

        print(f"Loop Agent -> Tyr: {next_message}")
        loop_messages.append({"role": "assistant", "content": next_message})

        try:
            tyr_reply, tyr_operation_id, tyr_state = send_to_tyr(tyr, next_message, tyr_operation_id)
        except TyrMCPError as e:
            tyr_reply, tyr_state = f"ERROR calling Tyr: {e}", "error"

        settled = tyr_state in TERMINAL_STATES
        if settled:
            label = "[Tyr Assistant replied]"
        else:
            label = (
                f"[Tyr Assistant has NOT finished yet -- gave up polling after "
                f"{POLL_MAX_ATTEMPTS} attempts, last known state={tyr_state!r}. "
                f"This may be stale/incomplete -- check again before treating it "
                f"as final]"
            )
            print(f"!! Not settled (state={tyr_state!r}) -- flagging as provisional.")

        print(f"Tyr -> Loop Agent: {tyr_reply[:400]}{'...' if len(tyr_reply) > 400 else ''}")
        loop_messages.append({"role": "user", "content": f"{label}: {tyr_reply}"})

        log({
            "phase": phase,
            "turn": turn,
            "operationId": tyr_operation_id,
            "to_tyr": next_message,
            "from_tyr": tyr_reply,
            "tyrState": tyr_state,
            "settled": settled,
        })

        divider()

    return loop_messages, tyr_operation_id


def render_transcript(loop_messages: list[dict]) -> str:
    return "\n\n".join(f"[{m['role'].upper()}] {m['content']}" for m in loop_messages[1:])


def _try_parse_plan(text: str) -> list[dict] | None:
    """Return a valid test-plan list parsed from text, or None."""
    import re
    candidates = [
        text,
        text.removeprefix("```json").removeprefix("```").removesuffix("```").strip(),
    ]
    # Also try extracting the first JSON array found anywhere in the text.
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        candidates.append(m.group())
    for candidate in candidates:
        try:
            plan = json.loads(candidate)
            if isinstance(plan, list) and all("id" in c and "title" in c for c in plan):
                return plan
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def generate_test_plan(brain: "OpenAI", loop_messages: list[dict]) -> list[dict]:
    """One-shot call (no Tyr interaction): design a test plan from what
    exploration turned up. Falls back to SEED_TEST_IDEAS if the model
    doesn't return parseable JSON."""
    plan_prompt = render_plan_prompt(render_transcript(loop_messages))
    raw = call_model(
        brain,
        [{"role": "user", "content": plan_prompt}],
        max_tokens=8192,  # ~50 test cases with instructions needs headroom
    )

    test_plan = _try_parse_plan(raw)
    if test_plan is None:
        print("!! Couldn't parse a test plan from the model -- falling back to seed ideas.")
        log({"phase": "plan", "warning": "unparseable test plan", "raw": raw})
        test_plan = SEED_TEST_IDEAS

    test_plan = ensure_mandatory_cases(test_plan)
    log({"phase": "plan", "test_plan": test_plan})
    return test_plan


def write_report(brain: "OpenAI", test_plan: list[dict], loop_messages: list[dict]) -> str:
    report_prompt = render_report_prompt(test_plan, render_transcript(loop_messages))
    report = call_model(
        brain,
        [{"role": "user", "content": report_prompt}],
        max_tokens=16384,  # one subsection per test case, up to ~50 cases
    )

    existing = [
        f for f in os.listdir(".")
        if f.startswith(_REPORT_PREFIX + "_") and f.endswith(".md")
    ]
    nums = []
    for f in existing:
        try:
            nums.append(int(f[len(_REPORT_PREFIX) + 1:-3]))
        except ValueError:
            pass
    next_num = max(nums, default=0) + 1
    report_file = f"{_REPORT_PREFIX}_{next_num}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    return report_file


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────


def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("Set OPENROUTER_API_KEY before running.")

    print(f"Python: {sys.executable}")
    print(f"Loop Agent model: {MODEL} (via OpenRouter: {OPENROUTER_BASE_URL})")
    print(f"Mode: {'ACTIONS ALLOWED (tyr_assistant_request)' if ALLOW_ACTIONS else 'READ-ONLY (tyr_assistant_query)'}")
    if ALLOW_ACTIONS:
        confirm_actions_enabled()

    try:
        tyr = TyrMCPClient()
        tyr.initialize()
    except TyrMCPError as e:
        sys.exit(str(e))

    brain = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        default_headers={"X-Title": "Tyr Loop Agent"},  # optional OpenRouter attribution
    )
    tyr_operation_id = None

    total_phases = 3 if SKIP_PLAN_PHASE else 4

    print(f"\n### Phase 1/{total_phases}: Explore ###")
    loop_messages = [{"role": "user", "content": "Begin exploring."}]
    if EXPLORE_TURNS > 0:
        loop_messages, tyr_operation_id = converse(
            brain, tyr, render_explore_prompt(STOP_TOKEN),
            loop_messages, tyr_operation_id, EXPLORE_TURNS, phase="explore",
        )
    else:
        print("Explore phase skipped (EXPLORE_TURNS=0).")

    if SKIP_PLAN_PHASE:
        test_plan = ensure_mandatory_cases(SEED_TEST_IDEAS)
        print(f"\nPlan phase skipped -- running {len(test_plan)} fixed scenario(s):")
    else:
        print(f"\n### Phase 2/{total_phases}: Design test plan ###")
        test_plan = generate_test_plan(brain, loop_messages)
        print(f"Designed {len(test_plan)} test cases:")
    for case in test_plan:
        print(f"  - [{case['id']}] {case['title']} ({case.get('category', '?')})")

    print(f"\n### Phase {total_phases - 1}/{total_phases}: Execute test plan ###")
    loop_messages.append({"role": "user", "content": "Begin executing the test plan."})
    loop_messages, tyr_operation_id = converse(
        brain, tyr, render_execute_prompt(test_plan, STOP_TOKEN),
        loop_messages, tyr_operation_id, MAX_TURNS, phase="execute",
    )

    print(f"\n### Phase {total_phases}/{total_phases}: Write report ###")
    report_file = write_report(brain, test_plan, loop_messages)
    print(f"Done. Log -> {LOG_FILE} | Report -> {report_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
