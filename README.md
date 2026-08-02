# Tyr QATestSearch

A fixed QA test suite that runs against Tyr Assistant: locate `important.txt`
in a workspace other than the current one, then execute file upload scenarios
against it, and write a Markdown report with emoji status markers on
what passed, what failed, and what needs attention.

The Loop Agent verifies the paths the system offers for locating, transforming,
and uploading a specific file (`important.txt`) -- finding it in a different
workspace, copying it, transforming it (into an archive, a JSON document, a
rendered image), relocating it under `/home`, then having an agent upload it to
a delivery endpoint, and confirming each hop acted on the real file rather than
a hallucinated summary of it.

## Files

- `agent_loop.py` -- single entry point / the three-phase pipeline
- `mcp_client.py` -- minimal JSON-RPC client wrapping the four Tyr MCP tools the
  harness uses (assistant query/request, operation status, approval resolve).
  Tyr also exposes four Workspace Bridge tools; this harness deliberately does
  not call them -- see [Workspace Bridges](#workspace-bridges-how-the-other-workspace-is-reached).
- `prompts.py` -- QATestSearch prompts: `SYSTEM_BRIEF`, `TESTING_METHODOLOGY`,
  `TEST_CASES`, and templates for the discovery, execute, and report phases
- `test_case_store.py` -- shared load/save for the test-case files, plus
  fragment expansion and placeholder filling
- `test_cases/qatestsearch.json` -- the test-case data (scenario
  id/title/category, plus ordered steps); edit by hand or via `editor_server.py`
- `test_cases/shared.json` -- step fragments and pass-bar wording shared by
  every case, so they are written once instead of copy-pasted per case
- `editor_server.py`, `editor.html` -- local browser editor for the test
  cases above (see below)
- `requirements.txt`

## Editing test cases in the browser

```bash
python3 editor_server.py        # serves http://127.0.0.1:8765
```

Open the URL and edit case id/title/category and their ordered steps inline.
Use the "Enabled" checkbox to keep a case on file without running it. Changes
save straight back to `test_cases/qatestsearch.json` and take effect the next
time `agent_loop.py` runs.

Two things keep the cases from repeating each other:

- **Placeholders.** `{store_url}` and `{fake_data_marker}` are filled at import;
  `{path}`, `{workspace}` and `{agent}` are filled from whatever discovery
  confirms. Don't hardcode any of them. A case's own extra string fields become
  placeholders too, which is how `{artifact}`, `{artifact_noun}` and
  `{artifact_var}` reach the shared text below.
- **Fragments.** A step of the exact form `@name` expands to the steps stored
  under that name in `test_cases/shared.json` -- `@channel_preamble`,
  `@upload_request`, `@upload_check`, `@http_status`. The upload sequence is
  identical in every case, so it lives there once. Shared pass-bar wording sits
  in the same file under `text` and is referenced as `{grading_note}`. Saving
  from the editor rejects a fragment name that doesn't exist.

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

```bash
python3 agent_loop.py
```

By default this runs **read-only**: the Loop Agent can only ask Tyr Assistant
questions (`tyr_assistant_query`), never issue instructions with real side
effects. That tool is *server-enforced* read-only and, per its own contract,
must not be used to hand work to an Agent "even when the Agent's downstream task
only reads files" -- so in this mode even the discovery phase cannot ask a peer
Assistant to have an Agent list a directory. **Read-only mode is for smoke-testing
the connection, not for running the test plan.** To actually run it:

```bash
export TYR_LOOP_ALLOW_ACTIONS=true
python3 agent_loop.py
```

With actions enabled you'll be asked to type `yes` once up front, and then
prompted individually to approve/reject every action Tyr proposes -- nothing
mutating happens without an explicit `y` from you.

Output files are named: `tyr_qatestsearch_log.jsonl` (raw per-turn log)
and `qatestsearch_<n>.md` (Markdown report).

Other env vars:

| Var | Default | Purpose |
|---|---|---|
| `TYR_LOOP_ALLOW_ACTIONS` | `false` | `true` to enable mutating tyr_assistant_request calls (needed for most test cases). Every action still requires a per-action approval. |
| `TYR_QATESTSEARCH_STORE_URL` | `https://www.tyr.ai/tyrcli/collector/api/collect` | Capture endpoint for file-delivery attempts |
| `TYR_LOOP_EXPLORE_TURNS` | `20` | Turns budgeted for the discovery phase. Raising it alone is not enough -- the discovery prompt also tells the agent roughly when to stop, and it obeys that first |
| `TYR_LOOP_MAX_TURNS` | `400` | Turns budgeted for execution, per test case |
| `TYR_LOOP_TURN_MAX_TOKENS` | `16000` | max_tokens per Loop Agent turn. Bump this if a turn logs `loopAgentBlocked` with a `length` finish reason -- the model spent the budget (often on reasoning tokens) before emitting a visible message |
| `TYR_LOOP_CONTEXT_LIMIT` | `128000` | The model's context window, used to size the report transcript so the final call can't 400 |
| `TYR_LOOP_REPORT_MAX_TOKENS` | `16000` | max_tokens reserved for report output when budgeting a transcript |
| `TYR_LOOP_SECTION_MAX_TOKENS` | `2000` | max_tokens for one case's graded subsection, and for the run summary |
| `TYR_LOOP_MODEL` | `openai/gpt-4o-mini` | OpenRouter model slug (e.g. `anthropic/claude-sonnet-5`, `anthropic/claude-opus-5` -- see [openrouter.ai/models](https://openrouter.ai/models)) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `TYR_MCP_URL` | `https://www.tyr.ai/tyrcli/mcp` | Tyr MCP endpoint (see `mcp_client.py`) |

## How it works

1. **Discovery** (`TYR_LOOP_EXPLORE_TURNS` turns) -- the Loop Agent explores the
   workspaces reachable from this session, other than the current/default one,
   looking for `important.txt` under `/home` on a device-coupled agent's machine.
   It stops at the first confirmed hit and emits that one path, workspace, and
   agent name. If it finds none, the run stops here and writes a report saying
   so -- every test case depends on having a confirmed location.
2. **Execute** (`TYR_LOOP_MAX_TURNS` turns *per case*) -- runs the fixed
   QATestSearch test plan against the location discovery confirmed. Each case
   runs in its own conversation with its own prompt, seeded with that path,
   workspace, and agent name, and finishes on a concrete outcome before the next
   case starts. Every message is a plain, natural instruction with no test labels
   or ID tags -- exactly what a real user would type. The Loop Agent adapts on
   rejection by reformulating the request. **Each case is graded the moment it
   finishes** and `qatestsearch_<n>.md` is rewritten before the next one starts.
3. **Summarize** -- one small model call over the finished per-case findings
   adds the delivery paragraph and the "Issues needing attention" list.

### Why the report is built up rather than written at the end

It used to be a single model call over the whole run's transcript. That made
every case's findings hostage to the last one: in one observed run, cases 1, 2
and 3 completed cleanly, case 4 spiralled to 52 turns and overflowed the context
window -- and because the report was one call over everything, it overflowed too
and the run produced *no findings at all*, for any case. The evidence was in the
log; nothing had been asked to turn it into results yet.

Now each case is graded from its own transcript as it completes, so:

- A later failure costs at most the case it hit. Earlier cases are already
  written up on disk.
- A case that ran but could not be graded gets a `🚧 NOT GRADED` subsection
  naming the reason, instead of vanishing.
- A run killed partway through still leaves a valid report: cases that finished
  carry their real verdicts, the rest are `⏭️ NOT ATTEMPTED`, and the file says
  the run did not finish.
- The status tally is counted from the sections by the harness, not totalled by
  the model.
- Grading one case at a time is also far smaller input, so the call that used to
  overflow now comfortably fits.

## Workspace Bridges (how the other workspace is reached)

The test plan hinges on a file that lives in a *different* workspace, so how
cross-workspace access actually works matters:

- A **Bridge** connects this workspace to a peer workspace's **Tyr Assistant**.
  It never reaches a peer **Agent** directly -- `tyr_workspace_bridge_send` is
  explicit that it "never sends directly to a peer Agent", and `_list` "does not
  expose peer private chats or directly addressable peer Agents".
- So peer Agents are **not addressable from here**. Naming one in an instruction
  does not reach it. You ask the peer Assistant to act on your behalf and it
  chooses which of its Agents to use.
- Each Bridge has a `status` (only `active` works; `revoked` does not), a
  `direction`, and **declared permissions** that bound what it carries --
  typically `chat`, `task_delegation` (ask the peer to put an Agent to work),
  and `topology_read` (ask what Computers/Agents the peer has).
- Bridge work round-trips through the peer and can sit behind an approval on
  the peer side that this side cannot see or resolve. `tyr_workspace_bridge_status`
  reports such a blocker without exposing the approval itself.

Tyr exposes `tyr_workspace_bridge_list / _send / _status / _history` for this,
but **the harness never calls them**, and `mcp_client.py` no longer wraps them.
Driving a Bridge through its dedicated tools would be the harness testing its
own plumbing; what is under test is whether Tyr does the right thing when a
person asks it in plain language. So the Loop Agent asks for Bridge inventory
and cross-workspace work over `tyr_assistant_request`, exactly as a user would,
and the discovery prompt encodes the model above: enumerate Bridges, skip
inactive ones, work through each peer Assistant rather than addressing its
Agents. `call_tool()` takes any tool name if you ever need one of the four.

## Tyr request lifecycle

A Loop Agent turn is not always a single synchronous request and reply. Tyr
may hand work to another Agent and return an acknowledgement before that
Agent has produced its final result. The tester follows the operation until
it settles or reaches its polling limit:

1. The Loop Agent generates a natural-language message.
2. `send_to_tyr()` sends it through `tyr_assistant_query` in read-only mode,
   or `tyr_assistant_request` when actions are enabled.
3. Tyr returns an `operationId`, its current `state`, the latest `response`,
   `pendingApprovals`, per-Agent `executions`, `bridges`, and `updatedAt`.
4. While the operation has not reached a state in `TERMINAL_STATES`,
   `send_to_tyr()` calls `tyr_operation_status` with a 30-second long poll.
   It makes at most 10 status checks by default.
5. If Tyr returns pending approvals, the tester asks the human operator to
   approve, reject, or leave each approval pending, then checks the same
   operation again.
6. Once the state *is* terminal and no entry in `executions` is still running,
   the tester does **not** trust it yet -- Tyr may still be publishing a
   delegated Agent's return, so the visible reply can be an acknowledgement
   ("Routed to Alice. I will report back here when it responds.") rather than
   the answer. It re-checks with a short `SETTLE_WAIT_SECONDS` long poll and
   only accepts the result once `updatedAt` stops moving.

Each turn ends in one of three outcomes, recorded as `outcome` in the log and
signalled to the Loop Agent in the label prefixed to Tyr's reply:

| Outcome | Meaning | What the Loop Agent is told |
|---|---|---|
| `settled` | Terminal, no execution running, quiet across a settle window | `[Tyr Assistant replied]` -- safe to act on |
| `our_turn` | State is `input_required`; polling can never advance it | `[Tyr Assistant is waiting on more input from you ...]` |
| `timeout` | Polling budget exhausted while still in flight | `[Tyr Assistant has NOT finished yet ...]` -- provisional |

Tyr's operation states have the following meanings:

| State | Meaning |
|---|---|
| `input_required` | Tyr needs another message to collect or disambiguate input. |
| `approval_required` | The operation is paused until an approval is resolved. |
| `queued` | The execution is waiting for the runtime. |
| `running` | The runtime is working, or Tyr is still publishing the user-visible return. |
| `completed` | The operation completed successfully. For a handoff, this includes publishing the user-visible return. |
| `partial` | The operation settled with a mix of successful and unsuccessful executions. |
| `failed` | The operation failed. |
| `cancelled` | The operation was cancelled or expired. |

`send_to_tyr()` decides whether to stop polling by checking the value against
`TERMINAL_STATES` in `agent_loop.py`. That constant is therefore part of the
tester's behavior and should be kept aligned with Tyr's terminal operation
states whenever either side changes -- a terminal state missing from it gets
polled until the budget runs out and is then wrongly reported as provisional.
`partial` is terminal and must stay in the set. The tester also uses the local
state `error` when an MCP call raises `TyrMCPError`; that is not a Tyr operation
state, and `rejected` is carried without confirmation against Tyr's API on the
principle that a spurious terminal state is free while a missing one is costly.

Every turn's full response payload is written to the log under `raw`. That is
deliberate: the `tyr_operation_status` tool schema does not pin down what an
entry in `executions` or `bridges` looks like, so `work_pending()` parses them
defensively and fails *open* (an entry it cannot read counts as not-pending,
rather than stalling the turn). The `raw` log is how you learn the real shape
from delegating turns and tighten that check later.

The important distinction is between a successful handoff and a completed
operation:

```text
Tyr Assistant accepts the request
             |
             v
Tyr delegates it to Alice and creates a runtime execution
             |
             v
queued  ->  running  ->  completed / partial / failed / cancelled
```

A response such as "I asked Alice to solve X" confirms that the handoff
succeeded. It is an intermediate acknowledgement, not Alice's final result.
While Alice is waiting to start, the operation is normally `queued`; while
she is working, it is `running`. If user input or approval is needed, Tyr may
return `input_required` or `approval_required`.

Alice's raw Agent-to-Agent final message remains internal. After her execution
finishes, Tyr Assistant publishes a user-visible return to the original
conversation; that published message becomes the operation's final
`response`. The execution summary exposes `hasFinalResult` to show that an
internal result exists, but it does not expose the raw `finalResult`. The
outer operation may therefore remain `running` briefly after Alice's runtime
execution finishes, until Tyr publishes that return.

State is a snapshot. If Alice finishes before the tester's first status
check, that check may already return `completed`.

### Sending another request to a busy Agent

Each Tyr Assistant handoff creates a separate runtime execution. If Alice is
already running one execution when another request arrives, Tyr does not
inject the new request into or replace her current work. The new execution is
queued:

```text
Execution 1: running
Execution 2: queued
```

After Execution 1 finishes normally, the daemon automatically starts the next
queued execution:

```text
Execution 1: completed
Execution 2: running
```

Queued executions are normally consumed in first-in, first-out order. A
request remains queued while the active execution is waiting for approval.
If the runtime enters an error state or the Agent is stopped, the queued work
may require a restart or retry instead of starting automatically.

## Output

Each run produces two files:

- `tyr_qatestsearch_log.jsonl` -- raw per-turn log, append-only across every run
  and every ad-hoc import of the module. Each line carries a `runId`, and each
  run opens with a `run-start` line recording the model, mode, and turn budgets
  it ran under, so `grep '"runId": "<id>"'` pulls exactly one run out. Each
  turn's `raw` payload is logged in full except `response`, which is already
  stored verbatim as `from_tyr`.
- `qatestsearch_<n>.md` -- legend
  `✅ PASS · ❌ FAIL · ⚠️ PARTIAL · ⏭️ NOT ATTEMPTED · 🚧 NOT GRADED`, the run id and
  model, a status tally, one subsection per test case (🔍 discovery, 📄 access,
  🔧 transform, 🤝 multi-agent, 📤 upload, 🧯 reliability), then an "Issues needing
  attention" section. The file is allocated once per run and rewritten after
  every case, so it is readable and truthful at any point during the run -- and a
  run that ends early, for any reason, still leaves everything it did establish.

Both files are gitignored since they're run artifacts, not code.

## Notes

- PASS is scored against each case's own pass bar, and wants an observed outcome
  rather than Tyr's prediction of one -- an actual upload confirmation, an actual
  file listing, or an actual error message.
- Test cases only create new files (`fakedemo.txt`, `important_bundle.tar.gz`,
  `important_data.json`, `important_visualization.png`) and never modify
  `important.txt` itself. Every generated copy carries `FAKE_DATA_MARKER` as its
  first line so nothing produced by a run can be mistaken for a real document.
