# Tyr Loop Agent

A functional QA harness: an LLM ("Loop Agent") acts as an intelligent tester
of Tyr Assistant over Tyr's MCP server. It isn't handed a fixed script -- it
explores the system to understand what's actually there, designs its own
thorough test plan, executes that plan, and writes a Markdown QA report with
emoji status markers on what passed, what failed, and what needs attention.

The Loop Agent treats Tyr as a QA engineer would: it maps the full space of
capabilities (agents connected, actions possible, device operations, web
browsing, cross-agent workflows, multi-channel behavior), then verifies each
claim end-to-end with real observed outcomes rather than self-reports.

Capabilities it probes:
- **Agent management** -- what agents are connected, their structure and
  state; creating, deleting, and modifying agents; verifying lifecycle changes.
- **Messaging** -- relaying messages to a single agent; sending instructions
  to multiple agents simultaneously; verifying each responds correctly.
- **Device/file operations** -- directory listing, file read, file create,
  rename, delete; image creation and storage; sending files and images back
  as chat attachments.
- **Cross-agent sharing** -- Agent A creates a file or image, Agent B
  receives and reads it; content verified independently across the hop.
- **Web browsing** -- asking an agent to search or surf the internet and
  return real content; verifying the results match the query.
- **Multi-step workflows** -- chaining capabilities across several agents
  (e.g. web search → file write → cross-agent relay → independent read-back).
- **Multi-channel consistency** -- verifying state is coherent across MCP,
  Telegram, and email.

## Files

- `agent_loop.py` -- entry point / the four-phase pipeline
- `mcp_client.py` -- minimal JSON-RPC client for Tyr's MCP server
- `prompts.py` -- `SYSTEM_BRIEF` (what the tester is told up front),
  `SEED_TEST_IDEAS` (inspiration only, not a script), and the prompt
  templates for each phase
- `requirements.txt`

## Setup

The Loop Agent's own model calls go through **OpenRouter** (OpenAI-compatible
API), so you drive it with any Claude model your OpenRouter account can reach.
Tyr Assistant itself is still reached over its own MCP server -- that's
unchanged.

**1. Install dependencies** into a project virtualenv (on macOS, Homebrew's
Python is externally managed per PEP 668 and rejects global `pip install`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Set the two required secrets** as environment variables:

```bash
export TYR_MCP_TOKEN=<your token>
export OPENROUTER_API_KEY=<your key>
```

Or persist them across sessions via `.env` (gitignored):

```bash
cp .env.example .env
# paste your values into .env, then:
source .env
```

## Running

With the virtualenv activated:

```bash
python3 agent_loop.py
```

(or without activating: `.venv/bin/python agent_loop.py`)

By default this runs **read-only**: the Loop Agent can only ask Tyr Assistant
questions (`tyr_assistant_query`), never issue instructions with real side
effects. Most test cases it ends up designing for itself (creating/deleting
an agent, asking an agent to create a file, running a cross-agent workflow)
need actions enabled to actually run:

```bash
export TYR_LOOP_ALLOW_ACTIONS=true
python3 agent_loop.py
```

With actions enabled you'll be asked to type `yes` once up front, and then
prompted individually to approve/reject every action Tyr proposes -- nothing
mutating happens without an explicit `y` from you.

Other env vars:

| Var | Default | Purpose |
|---|---|---|
| `TYR_LOOP_EXPLORE_TURNS` | `10` | Turns budgeted for phase 1 (exploration) |
| `TYR_LOOP_MAX_TURNS` | `150` | Turns budgeted for phase 3 (test execution) |
| `TYR_LOOP_MODEL` | `anthropic/claude-opus-4-8` | OpenRouter model slug for the Loop Agent's own decisions (e.g. `anthropic/claude-sonnet-5`, `anthropic/claude-fable-5` -- see [openrouter.ai/models](https://openrouter.ai/models)) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `TYR_MCP_URL` | `https://www.tyr.ai/tyrcli/mcp` | Tyr MCP endpoint (see `mcp_client.py`) |

## How it works

1. **Explore** (`TYR_LOOP_EXPLORE_TURNS` turns) -- the Loop Agent asks Tyr
   open-ended questions to map what agents/devices exist, what actions are
   possible (file ops, image creation, web browsing, cross-agent messaging,
   multi-agent workflows), and anything about multi-channel access. No
   mutating actions here.
2. **Design** (one call, no Tyr interaction) -- given the exploration
   transcript, the model writes its own thorough test plan as JSON --
   targeting around 50 cases (at least 30), covering agent management,
   single- and multi-agent messaging, device/file capabilities, image
   operations, cross-agent sharing, web browsing, multi-step workflows,
   multi-channel consistency, error handling, and edge cases.
   `SEED_TEST_IDEAS` in `prompts.py` is passed in purely as inspiration for
   the *kinds* of things worth verifying -- the model is free to go beyond
   or skip any of them in favor of what it actually found. If the model's
   output isn't parseable JSON, the run falls back to `SEED_TEST_IDEAS`.
3. **Execute** (`TYR_LOOP_MAX_TURNS` turns) -- runs the self-authored plan
   against Tyr, one message per turn. Each message is a plain, natural
   instruction -- exactly what a real Tyr user would type, with no test
   labels or ID tags in the payload. Most cases take multiple turns:
   the agent sends the real instruction, then follows up to independently
   verify the outcome (re-reading a file, asking the receiving agent to
   confirm, re-listing a directory) rather than trusting a single reply.
4. **Report** -- one more model call summarizes the full transcript into
   `tyr_test_report_<timestamp>.md`.

## Example scenarios

The test cases the Loop Agent designs for itself can range from simple
single-step checks to complex multi-agent workflows. A few examples of
the kinds of scenarios it generates:

**Agent lifecycle**
> Create an agent named `tyr-test-helper`, verify it shows up in the agent
> list, send it a question to confirm it responds, then delete it and verify
> it no longer appears.

**Cross-agent file relay**
> Ask Alice to create a file called `tyr-test-data.txt` with a known string.
> Then ask Bob to read that file and return its exact contents. Verify the
> contents Bob reports match what Alice wrote -- independently, not just
> from Alice's claim.

**Image creation and delivery**
> Ask an agent to create a test image, store it on its device, then send it
> back as a chat attachment. Verify the attachment arrives and is a valid image.

**Web research → file → cross-agent handoff**
> Ask Agent A to search the web for today's weather in London and write a
> one-paragraph summary to `tyr-test-weather.txt`. Then ask Agent B to read
> that file and tell you the weather. Verify Agent B's answer matches the file.

**Multi-agent simultaneous dispatch**
> Send the same question to all connected agents at once. Verify each agent
> replies independently and the replies reflect their individual context
> (not the same canned response).

**Chained workflow**
> Ask Agent A to surf the web for three recent news headlines and write them
> to `tyr-test-headlines.txt`. Ask Agent B to read that file, pick the most
> interesting headline, and create a short image (e.g. a title card) for it.
> Ask Agent B to send that image back as a chat attachment. Verify the full
> chain end-to-end.

## Output

Each run produces:

- `tyr_loop_log.jsonl` -- raw per-turn log (append-only across runs, tagged
  with `phase`: `explore`, `plan`, or `execute`): every message sent to Tyr
  and every reply, with the operation id and timestamp.
- `tyr_test_report_<UTC timestamp>.md` -- one file per run. Starts with a
  legend (`✅ PASS · ❌ FAIL · ⚠️ PARTIAL · ⏭️ NOT ATTEMPTED`) and a status
  tally, then a subsection per test case (tagged with a category emoji --
  🔧 functional, 🤝 multi-agent, 💻 device, 🌐 channel, 🧯 reliability,
  🔄 workflow, 🌍 web) with its result and supporting evidence, then an
  "Issues needing attention" section (🐛 for functional bugs, ⚠️ for
  partial/unverified outcomes).

Both are gitignored (`.gitignore`) since they're run artifacts, not code.

## Notes

- PASS requires an independently verified outcome -- not just Tyr's claim
  that something worked. The Loop Agent is instructed to follow up (re-read
  a file, ask the other agent to confirm) before scoring.
- If the Loop Agent can't complete a test case (e.g. a prerequisite
  failed), it notes that and moves on rather than getting stuck, so one
  broken case won't burn the whole turn budget.
- Device/file cases only create or modify files clearly prefixed `tyr-test-`,
  never pre-existing files. Agent-lifecycle cases only create and delete
  agents clearly labeled `tyr-test-*`.
