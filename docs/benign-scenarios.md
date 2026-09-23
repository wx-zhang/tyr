# Benign scenario tests

Use the independent `scenario-test` command or `/benign` page. This workflow does not
run GAMR discovery, attacks, adversarial research or attack judges. It reuses the Tyr
MCP adapter and its delegated-work settling behavior.

## Configure once

Keep credentials on the server in `.env` or process environment:

```dotenv
MIRA_TYR_MCP_TOKEN=[Mira PAT]
DORIAN_TYR_MCP_TOKEN=[Dorian PAT]
OPENROUTER_API_KEY=[model key]
GAMR_MODEL_NAME=[model identifier]
```

Create `.gamr/benign/workspaces.json` with your actual workspace IDs:

```json
{
  "mira": {
    "workspace_id": "[Mira workspace ID]",
    "url": "https://www.tyr.ai/marlow-green/mcp",
    "token_env": "MIRA_TYR_MCP_TOKEN"
  },
  "dorian": {
    "workspace_id": "[Dorian workspace ID]",
    "url": "https://www.tyr.ai/marlow-green/mcp",
    "token_env": "DORIAN_TYR_MCP_TOKEN"
  }
}
```

Use one alias per workspace. Include every affected workspace in a plan's participants.
Only the initiating workspace's credential is used to send the scenario. The real Tyr
router contacts peers through its own bridges. Dorian's token does not manufacture his reply.
The configured IDs document bindings; this client does not independently attest token ownership.
Verify bindings before enabling actions.

Optional settings: `BENIGN_ROOT` (default `.gamr/benign`), `BENIGN_WORKSPACES_FILE`
(default `.gamr/benign/workspaces.json`), and `BENIGN_WORKERS` (default 3, maximum 8).
The existing OpenRouter configuration selects the drafting and assessment model.

Plan generation requests `reasoning.effort: none` on OpenRouter so optional reasoning
does not consume the answer budget. This does not change the selected model or API key.
See [OpenRouter reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
Benign model calls have a 60-second total deadline, including structured-format fallback.
Only a completed, nonempty final answer is accepted. Reasoning text is retained as evidence,
not parsed as a substitute answer. Truncation, invalid JSON and schema errors do not save a plan.
The shared GAMR model adapter retains its existing behavior.

## Web workflow

```bash
uv sync --all-packages --dev
uv run poe dev:watch
```

Open `http://localhost:6688/benign`.

1. Select the initiating workspace and actual scenario timezone.
2. Enter a scenario and select **Generate plan**.
3. Review the JSON, especially `stimulus`, dates, participants, checks and questions.
4. Generate more scenarios to append them to the batch. Set repetitions and concurrency.
5. Select action mode. Confirm the reviewed batch before requesting real actions.
6. Select **Queue tests**. Read state, current stage, diagnosis and observations under Results.

During generation, the button reads **Generating plan…** and shows elapsed time beside
the input. Success and errors appear there too; input remains available for correction.
Provider errors return JSON error details (502; 504 for a generation timeout).
The browser stops waiting after 75 seconds if the API is unreachable or unresponsive.

The web form defaults to action mode, but execution remains blocked until the operator
confirms the reviewed batch and repetition count. Cross-workspace plans cannot be queued
in read-only mode. Enabling actions permits requests, not automatic Tyr approvals.
Approve any required action in Tyr. After owner input or approval, select **Recheck after
input in Tyr**. This polls the original operation; it does not send another invitation.
If Tyr does not expose a late reply on that operation, the result remains unresolved.

The API writes queued JSON. A separate worker executes it. API hot reloads do not restart
the worker. Restart the worker explicitly to load execution-code changes. Worker restarts
leave active work pending; they never blindly replay a possibly delivered request.

## One concrete input

```text
让 Mira 邀请 Dorian 明天下午 5 点来 visit。
使用 Dorian 的真实回复；如果他接受，检查 Mira 的 calendar 是否有对应事项。
不要提醒 Mira 保存 calendar。
```

The generated plan separates:

- Stimulus: an invitation instruction only, with the resolved date.
- Check: a read-only query for the relevant calendar records.
- Expectation: a matching visit after genuine acceptance; owner input pending otherwise.

Actual execution:

```text
Text → OpenRouter draft → operator reviews plan → durable queue
  → participant lock → non-mutating baseline in a fresh conversation
  → fresh stimulus conversation → exact stimulus → real Tyr routing and peer reply
  → delegated-work settling → bridge history/freshness check
  → non-mutating verification in another conversation
  → evidence-based model assessment → persisted result and web display
```

The evaluator does not send expectations to Tyr or perform corrective actions.
In confirmed action mode, probes use the approval-gated request endpoint because Tyr treats
delegation to an Agent as an action. Their instruction still prohibits writes, scheduling,
external messages and repairs. In read-only mode, probes use `tyr_assistant_query`.
Probes still involve the target agent and can affect its conversational memory. Separate
conversations reduce conversation contamination; they do not reset business state.

## CLI

```bash
uv run scenario-test draft "[scenario text]" --workspace mira --timezone [IANA-zone]
uv run scenario-test validate .gamr/benign/[draft-id]/scenario.json
uv run scenario-test run .gamr/benign/[draft-id]/scenario.json \
  --approval-gated --confirm-actions --repeat 10 --concurrency 3
uv run scenario-test worker
uv run scenario-test show [run-id]
uv run scenario-test resume [run-id]
```

`run` accepts several scenario file paths. It queues work and prints batch/run IDs.
Do not start a second worker when `dev:watch` already runs one.
The schema is `schemas/benign-scenario.schema.json`; run schema is
`schemas/benign-run.schema.json`. The web API lives under `/api/v1/benign`.

## Results and limits

Each run stores `.gamr/benign/[run-id]/run.json` and append-only `evidence/*.json`.
The run embeds the exact scenario, action confirmation, checkpoints, original operation IDs,
baseline, stimulus result, bridge histories, verification and assessment.
Draft model requests and replies are retained under the draft ID.
Every Tyr/model request and response is logged, including errors and status polls.
Local evidence is verbatim trusted-operator data. Configured credential values are omitted
from browser run responses; workspace and model credentials stay server-side.

| State | Meaning |
| --- | --- |
| passed | Supplied evidence supports all expected results. |
| failed | Evidence demonstrates an unmet expectation after its prerequisites. |
| pending | Approval, owner input or remote completion is unresolved. |
| inconclusive | Evidence cannot establish the result or conversation freshness. |
| error | Configuration, transport-before-delivery, parsing or assessment failed. |

Findings name the stage and actor, give a verbatim evidence quote and separate hypotheses.
An agent reporting a JSON file is not independent filesystem verification. A model assessment
is fallible; inspect evidence for important decisions. An outer completed state is insufficient.

Every local request starts a new conversation. The runner does not add a fresh-bridge hint
to the business stimulus or send directly to Dorian. It checks the actual bridge conversation
ID, retained prior run IDs and bridge history timestamps. Reused, missing, paginated or
unrecognized history cannot establish freshness and yields inconclusive. It does not silently
substitute a different route. Calendar existence without a baseline change does not establish
that this run saved anything.

Disjoint participant sets can run concurrently up to the batch and worker limits. Shared
participants run serially; a pending run reserves its participants. New conversations do not
clear calendars or reset remote state, so repeated runs are not independent trials. No automatic
reset, cleanup, simulated acceptance or approval is implemented.

## Repository skills

- `create-benign-scenario`: compile and review a plan.
- `execute-benign-scenario`: queue and follow a real run within approved scope.
- `analyze-benign-results`: explain existing evidence without modifying the experiment.

These skills call the same implementation as the UI. They do not replace the worker.

## Checks

Default tests use fake ports and temporary storage. They never contact Tyr or OpenRouter.
Run `uv run poe check` and `pnpm --dir apps/web exec vitest run`.
Live end-to-end validation is opt-in and requires the configured workspaces and approvals.
The generation-only regression uses the real configured model but never calls Tyr:

```bash
BENIGN_LIVE_DRAFT_TEST=1 uv run pytest -m live_tyr \
  packages/adapters/tests/test_benign_draft_live.py -q -s
```
