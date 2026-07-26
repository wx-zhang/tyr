"""
Prompt templates for the Tyr Loop Agent QA harness.

The Loop Agent is a functional QA tester: SYSTEM_BRIEF tells it what kind
of system Tyr Assistant is, but it isn't handed a fixed checklist. The run
has four phases, each with its own prompt template below:

  1. EXPLORE  -- a few open-ended turns to map Tyr's real capabilities
                 (agents, devices, actions, channels).
  2. PLAN     -- one call, no Tyr interaction: given the exploration
                 transcript, write a test plan of its own. SEED_TEST_IDEAS
                 is passed along only as inspiration for the *kinds* of
                 things worth verifying, not a script to follow.
  3. EXECUTE  -- work through the self-authored plan against Tyr, one
                 message per turn.
  4. REPORT   -- summarize results as Markdown, with emoji status markers.
"""

SYSTEM_BRIEF = """
What you already know about the system under test (Tyr Assistant):

- Tyr Assistant is the head orchestrator of a multi-agent system. It sits in
  front of a number of downstream Agents, each of which may have real
  capabilities on their connected device/machine or environment.
- Tyr can relay instructions to agents: ask one agent to do a task, have
  agents communicate with each other, or coordinate across several agents
  at once -- including sending instructions to multiple agents simultaneously.
- Agents may be able to navigate and list directory contents, read file
  contents, create/rename/modify/delete files, create images, store images,
  and send documents or images back to you as chat attachments.
- Agents may be able to send files or images to other agents. An agent on
  one device may be able to receive a file or image that a different agent
  on a different device created.
- Agents may be able to surf the internet -- browse URLs, search the web,
  retrieve content -- and report back their findings.
- Tyr can orchestrate multi-step workflows where one agent's output feeds
  into another's input across multiple turns.
- Tyr may support creating new agents, modifying existing ones, or deleting
  them from the workspace.
- Tyr is reachable over more than one channel -- this MCP connection, but
  also Telegram and email -- into the same underlying system and agents.

You do NOT know the real agent names, device names, or exact capabilities
yet -- that's what exploration is for. Your job is to map what Tyr can
actually do across all its agents and features, then verify each capability
end-to-end as a QA tester.
""".strip()


SEED_TEST_IDEAS = [
    {"id": "agent-inventory", "title": "List all connected agents and their details", "category": "functional"},
    {"id": "agent-structure", "title": "Understand the agent hierarchy and relationships", "category": "functional"},
    {"id": "send-message-single", "title": "Relay a message to a specific agent and verify a meaningful reply", "category": "functional"},
    {"id": "send-message-multi", "title": "Send an instruction to multiple agents simultaneously and verify each responds", "category": "multi-agent"},
    {"id": "create-agent", "title": "Create a new test agent and verify it appears in inventory", "category": "functional"},
    {"id": "delete-agent", "title": "Delete a test agent and verify it no longer appears", "category": "functional"},
    {"id": "agent-directory-list", "title": "Ask an agent to list a directory on its machine and return filenames", "category": "device"},
    {"id": "agent-file-read", "title": "Ask an agent to read and return the contents of a specific file", "category": "device"},
    {"id": "agent-file-create", "title": "Ask an agent to create a file with known content, then verify by reading it back", "category": "device"},
    {"id": "agent-file-rename", "title": "Ask an agent to rename a test file, then verify via directory listing", "category": "device"},
    {"id": "agent-file-delete", "title": "Ask an agent to delete a test file, then verify it is gone", "category": "device"},
    {"id": "agent-image-create", "title": "Ask an agent to create an image and return it as an attachment", "category": "device"},
    {"id": "agent-image-store", "title": "Ask an agent to store an image to its device and confirm it is there", "category": "device"},
    {"id": "agent-send-file-attachment", "title": "Ask an agent to send a test file back as a chat attachment and verify it arrives", "category": "functional"},
    {"id": "agent-send-image-attachment", "title": "Ask an agent to send an image back as a chat attachment and verify it arrives intact", "category": "functional"},
    {"id": "inter-agent-file-send", "title": "Have Agent A create a file and send it to Agent B; verify Agent B received it with matching content", "category": "multi-agent"},
    {"id": "inter-agent-image-send", "title": "Have Agent A create an image and send it to Agent B; verify Agent B received it", "category": "multi-agent"},
    {"id": "agent-web-search", "title": "Ask an agent to search the web for a specific topic and return findings", "category": "web"},
    {"id": "agent-web-to-file", "title": "Ask an agent to search the web and write a summary to a file; verify the file content", "category": "workflow"},
    {"id": "multi-agent-workflow", "title": "Agent A fetches web data, Agent B writes it to a file, verify the file via directory listing + read", "category": "workflow"},
    {"id": "cross-agent-file-relay", "title": "Agent A creates a file; Agent B reads it and summarizes -- verify Agent B's summary matches the file", "category": "multi-agent"},
    {"id": "error-handling", "title": "Send a malformed or invalid request and verify Tyr returns a clear error", "category": "reliability"},
    {"id": "unknown-agent", "title": "Ask for an agent that does not exist and verify a clear, correct error response", "category": "reliability"},
    {"id": "multi-channel", "title": "Verify that agents/state visible via MCP are consistent when queried via another channel", "category": "channel"},
]


CATEGORY_EMOJI = {
    "functional": "🔧",
    "multi-agent": "🤝",
    "device": "💻",
    "channel": "🌐",
    "reliability": "🧯",
    "workflow": "🔄",
    "web": "🌍",
}


TESTING_METHODOLOGY = """
Test cases must be EXECUTED, not just asked about. For every case, send the
real instruction you'd send if you genuinely wanted the thing to happen:
actually ask an agent to list a directory and get back the real filenames;
actually ask one agent to send a file to another and confirm it arrived;
actually ask an agent to search the web and get real content back.

Do NOT substitute a meta-question ("would you be able to do X?", "is it
possible to...?") for the real attempt, and do not treat Tyr Assistant's
self-description of its own capabilities as sufficient evidence. Self-reports
are useful during exploration for orientation, but a test case is only PASS
or FAIL once you have an observed, concrete outcome -- actual returned data,
an actual file listing, actual content, or an actual error message -- not a
prediction of one. If a reply describes what would happen instead of doing
it, follow up asking for the real attempt before scoring.

Many cases are inherently multi-turn: send the real instruction, then keep
following up (verify the file was actually created, ask the other agent to
independently confirm it received the content, re-list the directory, re-read
the file) until the outcome is actually confirmed rather than just claimed by
one reply. Don't score a case off a single unconfirmed reply if a follow-up
verification is available and you haven't run it yet.

For multi-agent workflow cases: don't trust either agent's self-report of
its own success -- use an independent check (have the receiving agent
actually read back the file content and report it, rather than relying on
the sending agent saying "I sent it").

If a test case's prerequisite failed, say so, move on, and note it rather
than getting stuck.
""".strip()


# ─────────────────────────────────────────────────────────────
# PHASE 1: EXPLORE
# ─────────────────────────────────────────────────────────────

EXPLORE_PROMPT_TEMPLATE = """
You are the Loop Agent, a functional QA tester of a system called "Tyr
Assistant". You talk to it one message at a time and read its reply.

{system_brief}

Your job right now is ONLY to explore -- do not test or verify anything yet.
Spend your turns mapping the system:
- What agents are connected, their names, states, and what they can do.
- What kinds of actions Tyr can orchestrate: relay messages to agents,
  create/delete/modify agents, send instructions to multiple agents at once.
- For any device-coupled agent: what file/device-level operations it
  supports -- listing directories, reading file contents, creating/renaming/
  deleting files, creating images, storing images, sending documents or
  images back as chat attachments.
- Whether agents can send files or images to other agents on different devices.
- Whether agents can browse the internet (surf URLs, search the web) and
  report back their findings.
- Tyr's ability to coordinate multi-step workflows across several agents.
- Any information about multi-channel access (Telegram/email/MCP) and
  whether state is consistent across channels.

Rules:
- Send ONE message per turn. Keep it short and specific.
- Ask real questions -- don't narrate what you're doing.
- Do not attempt to create, delete, or modify anything during exploration.
- If a reply is tagged "has NOT finished yet", it's provisional -- follow up
  before relying on it.
- When you feel you understand enough to design a thorough test plan (or
  after a handful of turns), respond with exactly: {stop_token}

Respond with ONLY the next message to send to Tyr Assistant (no preamble,
no quotes) -- or with {stop_token} if you're done exploring.
""".strip()


def render_explore_prompt(stop_token: str = "<<DONE>>") -> str:
    return EXPLORE_PROMPT_TEMPLATE.format(system_brief=SYSTEM_BRIEF, stop_token=stop_token)


# ─────────────────────────────────────────────────────────────
# PHASE 2: PLAN
# ─────────────────────────────────────────────────────────────

PLAN_PROMPT_TEMPLATE = """
{system_brief}

Here's what you learned from exploring the real Tyr Assistant just now:

{transcript}

For inspiration only (not a checklist -- your plan should reflect what you
actually learned above, using real names/details where you have them, and
can go beyond or skip any of these):

{seed_ideas}

{testing_methodology}

Each case's "instruction" field must read as a real action/message to
actually send -- phrased as a genuine request or instruction, not a question
about whether it would work (e.g. write "Ask Agent Bob to list the contents
of the /home directory and return the filenames", not "Ask whether Bob can
list files"). Say what real, observable evidence would count as a pass vs a
fail for each case.

A significant portion of your test cases should be intricate, multi-step
scenarios involving more than one agent or action in sequence -- not just
simple one-shot checks. Good multi-step cases look like: "Ask Agent A to
search the web for X and write results to a file → ask Agent B to read that
file and extract key points → ask Agent B to send those points as an
attachment → verify content matches end-to-end." or "Create a test agent,
give it a task that requires it to coordinate with another agent, verify the
output on both ends, then clean up." These compound cases are where real
integration bugs surface. For each multi-step case, the instruction should
describe the full sequence of steps, and the pass/fail criterion should
require verification at the end of the chain -- not just the first step.

Write your own test plan: a THOROUGH plan of around 50 test cases, never
fewer than 30. Spread cases across all of the following, with multiple cases
per bucket:

- Agent discovery and management -- inventory, structure, create/delete
  agents, verify each action actually took effect in the inventory
- Single-agent messaging -- relay different kinds of requests to a specific
  agent and verify the replies are meaningful and correct
- Multi-agent messaging -- send instructions to multiple agents simultaneously
  and verify each responds correctly and independently
- Device/file capabilities -- directory listing, file read, file create, file
  rename, file delete; verify each via an independent follow-up (re-list the
  directory, re-read the file) rather than trusting a claimed success
- Image capabilities -- create an image, store an image, send an image back
  as an attachment; verify the image actually arrives and is correct
- Cross-agent file and image sharing -- Agent A creates a file/image and
  sends it to Agent B; verify Agent B actually received it with matching
  content, independently confirmed
- Internet/web capabilities -- ask an agent to browse or search the web and
  return findings; verify the content actually relates to the query
- Multi-step workflows -- chain several capabilities together (e.g. web
  search → file write → cross-agent relay → independent verification); these
  are the most revealing cases for a real functional picture of the system
- Multi-channel consistency -- if you learned anything about Telegram/email/
  MCP, verify state created via one channel appears correctly in another
- Error handling and reliability -- invalid requests, unknown agent IDs,
  malformed instructions; verify clear and correct error responses
- Edge cases -- empty/very long input, ambiguous instructions, duplicate
  requests, boundary conditions (delete something already deleted, create a
  duplicate, send an image to an agent that may not support it)

Prefer specific, concrete instructions using real agent/device names you
discovered. If any agent is coupled to a device, include several device/file
capability cases. If agents can browse the internet, include cases that verify
real content comes back. Multi-step workflow cases should test at least two or
three agents working in sequence. Vary the phrasing and angle across cases
that target the same capability so you're not just repeating one test.

Safety constraint for device/file cases: only create, rename, modify, or
delete files the agent creates for the test itself (clearly named, e.g.
prefixed `tyr-test-`) -- never touch a pre-existing file on a device. When
testing attachments, only send documents/content created for the test.

Safety constraint for agent-lifecycle cases: only create clearly
test-labeled agents (e.g. named/prefixed `tyr-test-`) and delete them at
the end of the case -- never delete or modify agents that already existed
before this test run.

Respond with ONLY a JSON array of roughly 50 objects (never fewer than 30),
no markdown fences, no preamble, in this exact shape:
[
  {{"id": "kebab-case-id", "title": "Short title", "category": "functional|multi-agent|device|channel|reliability|workflow|web", "instruction": "The real message/request to actually send, plus what real observed evidence counts as a pass vs a fail"}}
]
""".strip()


def render_plan_prompt(transcript: str) -> str:
    return PLAN_PROMPT_TEMPLATE.format(
        system_brief=SYSTEM_BRIEF,
        transcript=transcript,
        seed_ideas=render_test_plan(SEED_TEST_IDEAS),
        testing_methodology=TESTING_METHODOLOGY,
    )


# ─────────────────────────────────────────────────────────────
# PHASE 3: EXECUTE
# ─────────────────────────────────────────────────────────────

EXECUTE_PROMPT_TEMPLATE = """
You are the Loop Agent, a functional QA tester. You hold a back-and-forth
conversation with Tyr Assistant by sending it one message at a time and
reading its reply, in order to run the test plan below -- which you designed
yourself based on exploring this system.

Test plan:
{test_plan}

{testing_methodology}

Rules:
- A "turn" is ONE message to Tyr Assistant, then reading its reply before
  deciding your next message -- keep each individual message short and
  specific. That does NOT mean one turn per test case: most cases need
  several turns. Fully finish (or conclude you can't proceed on) one test
  case before moving to the next.
- Send the real instruction, phrased as a genuine request -- not "would you
  do X" or "is X possible". If a reply describes/predicts an outcome instead
  of actually doing the thing, push for the real attempt ("go ahead and
  actually do that now, then tell me exactly what happened") before moving on.
- Don't stop at the first reply: keep taking turns until you have a confirmed,
  observed outcome (actual data/file/error returned), not just a claim. Use
  an independent check where available (re-list the directory, have the
  receiving agent read back the content) rather than trusting a single
  agent's self-report of its own success.
- Send only the plain message or instruction at hand -- no test ID labels,
  no meta-commentary about what you're testing. Write exactly what a real
  user of Tyr would type.
- If a test case's prerequisite failed, note it, move on, and don't get stuck.
- If a reply is tagged "has NOT finished yet", it's provisional -- follow up
  before scoring that case.
- Do not repeat a question already answered.
- When every test case has been attempted, respond with exactly: {stop_token}

Respond with ONLY the next message to send to Tyr Assistant (no preamble,
no quotes) -- or with {stop_token} if you're done.
""".strip()


def render_execute_prompt(test_plan: list[dict], stop_token: str = "<<DONE>>") -> str:
    return EXECUTE_PROMPT_TEMPLATE.format(
        test_plan=render_test_plan(test_plan),
        stop_token=stop_token,
        testing_methodology=TESTING_METHODOLOGY,
    )


# ─────────────────────────────────────────────────────────────
# PHASE 4: REPORT
# ─────────────────────────────────────────────────────────────

REPORT_PROMPT_TEMPLATE = """
You just finished running the self-designed test plan below against Tyr
Assistant. Below that is the full transcript (exploration + execution).

Test plan:
{test_plan}

Transcript:
{transcript}

Write a concise Markdown QA report. Keep it tight -- one line of evidence
per case, no padding.

# Tyr Assistant QA Report

`Legend: ✅ PASS · ❌ FAIL · ⚠️ PARTIAL · ⏭️ NOT ATTEMPTED`

One sentence on overall findings. Status tally: `✅ N  ❌ N  ⚠️ N  ⏭️ N`.

## Results

For every test case, one subsection using this format:

`### <category emoji> <id> -- <title>`

Category emoji mapping: {category_legend}.

Under each subsection, two lines only:
- `**Result:** ✅ / ❌ / ⚠️ / ⏭️`
- `**Evidence:** one sentence -- the concrete thing that happened (actual
  output, file content, error message, or what was missing). If the outcome
  is only a self-report with no independent verification, say so here.

## Issues needing attention

One bullet per FAIL or PARTIAL: 🐛 functional bug, ⚠️ partial/unverified.
State the problem in one line. ✅ if nothing failed.
""".strip()


def render_report_prompt(test_plan: list[dict], transcript: str) -> str:
    category_legend = ", ".join(f"{cat} {emoji}" for cat, emoji in CATEGORY_EMOJI.items())
    return REPORT_PROMPT_TEMPLATE.format(
        test_plan=render_test_plan(test_plan),
        transcript=transcript,
        category_legend=category_legend,
    )


# ─────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────


def render_test_plan(test_plan: list[dict]) -> str:
    lines = []
    for i, case in enumerate(test_plan, start=1):
        category = case.get("category", "functional")
        emoji = CATEGORY_EMOJI.get(category, "\U0001f9ef")
        detail = case.get("instruction") or case.get("title", "")
        lines.append(f"{i}. {emoji} [{case['id']}] {case['title']} -- {detail}")
    return "\n".join(lines)
