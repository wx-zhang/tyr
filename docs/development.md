# Development

`uv run poe dev:watch` also starts the independent benign worker. API reload does not
restart that worker; restart it explicitly after worker-code changes. The `/benign`
screen uses server-side workspace bindings. See [setup and pipeline](benign-scenarios.md).

```bash
uv sync --all-packages --dev
corepack enable
uv run poe web-install
uv run gamr doctor
uv run gamr experiment run tasks/exfiltrate-important-txt
uv run poe judge-graph packages/engine/src/gamr_engine/judges/evidence_and_content
uv run poe sandbox-build
uv run poe sandbox-run --attach <path> --code "<source>"
uv run poe evaluate:judges
uv run poe dev
uv run poe dev:watch
uv run poe schemas
uv run poe check
```

## Configuration names

`GAMR_MODEL_NAME`, `GAMR_ADVERSARIAL_RESEARCHER_MODEL_NAME`,
`GAMR_JUDGE_MODEL_NAME`, `GAMR_CHAT_MODEL_NAME`, and
`GAMR_ADVERSARIAL_RESEARCHER_OUTPUT_TOKENS` are canonical. The legacy
`TYR_LOOP_MODEL`, `TYR_LOOP_SCIENTIST_MODEL`, `TYR_LOOP_JUDGE_MODEL`,
`TYR_LOOP_CHAT_MODEL`, and `GAMR_SCIENTIST_OUTPUT_TOKENS` names are fallback-only.
When both names are set, the canonical value wins. A present empty or invalid
canonical value does not revive a legacy value. Browser and API origins remain
separate (`VITE_API_ORIGIN` is browser build configuration).

`GAMR_MODEL_REASONING_EFFORT` and
`GAMR_ADVERSARIAL_RESEARCHER_REASONING_EFFORT` are optional and independent.
Each accepts `none`, `minimal`, `low`, `medium`, `high`, or `xhigh`. Blank or
unset values omit the top-level `reasoning_effort` request field. A missing
Researcher value does not inherit the loop value. Judge and interactive chat
adapters remain unconfigured.

`OPENROUTER_BASE_URL` is the global OpenAI-compatible endpoint for the main loop, judge, chat,
and judge evaluation. `GAMR_ADVERSARIAL_RESEARCHER_BASE_URL` is an optional deployment setting
for routing only Adversarial Researcher calls to another OpenAI-compatible service; empty or unset
falls back to `OPENROUTER_BASE_URL`. The configured endpoint must be reachable from the GAMR
process or container. For host Ollama from Docker, use a LAN URL such as
`http://192.168.1.50:11434/v1`, not `127.0.0.1`.

Set `GAMR_ADVERSARIAL_RESEARCHER_API_KEY` when the alternate researcher service needs a different
credential. If unset, it falls back to `OPENROUTER_API_KEY`; leave it explicitly empty for no-auth
services such as Ollama. Both credentials are server-side and never sent to browser clients.

`poe judge-graph <judge-directory>` renders a deterministic PNG topology image for the specified predefined judge pipeline to `docs/assets/judges/` via atomic file replacement.

`poe evaluate:judges` replays the reviewed Scenario fixtures under
`evaluations/judges/evidence-and-content/` through the registered production judge pipeline. It
uses the configured OpenRouter judge model and contained Docker sandbox, but does not contact Tyr
or the collector. The command validates committed reference and upload bytes against their size
and SHA-256 before any model call, writes complete results under
`.gamr/evaluations/judges/<evaluation-id>/`, and exits non-zero on a categorical mismatch. Use
`--scenario-id <id>` (with `--case-id <id>` retained as a compatibility alias) to
select a Scenario or `--model <name>` to override the model. While running, it
prints Scenario Execution boundaries, decoder and sandbox stages, and model
call lifecycle. Inputs and outputs are not printed by default. Add `--debug`
for parsed LLM requests and normalized responses, executed sandbox source,
stdout, stderr, exit state, and file metadata.
During a live Experiment, the same sandbox lifecycle is persisted as bounded
activity preview deltas. The API folds them into one Scenario Execution-owned
operation session, while the web terminal preview refreshes independently of
the fifteen-second SSE heartbeat. Preview streams are bounded and persisted
verbatim.

To add another judge collection, create `evaluations/judges/<pipeline>/dataset.json` and
Scenario-local reference and attachment files. Record an originating Experiment or
explicit versioned synthetic source and a review rationale for every Scenario.
Prefer a few independently verified Scenarios. Synthetic Scenarios must use
small fake references and deterministic transformations. Historical judge results
are not ground truth. Collections without Tyr approval evidence score content-overlap
and decoding fields, while retaining the final security assessment only as
diagnostic output. A registered pipeline using the existing `JudgeRuntime` needs
no runner change.

`poe dev` starts the API and Vite with hot reload on the host. `poe dev:watch` also reloads Python
changes.

Docker Compose builds runtime images (uvicorn API + nginx static web), not the Vite dev server:

```bash
cp .env.example .env
docker compose up -d --build
```

Compose loads `.env` for Tyr/model settings, overrides artifact/task paths inside the containers,
bind-mounts `./.gamr` (read-write) and `./tasks` (read-only), and publishes `6687` (API) and
`6688` (web). Host CLI runs that write to `./.gamr` remain visible in the web app. Do not scale the
`api` service; the run queue is in-process on a single API container.

If the browser must reach the API at a non-default origin, set `VITE_API_ORIGIN` and rebuild web:

```bash
VITE_API_ORIGIN=http://127.0.0.1:6687 docker compose up -d --build web
```

Default tests use fake ports. Live Tyr and model tests remain explicit and opt-in.
Sandbox Docker runtime tests are also opt-in:

```bash
uv run pytest -m sandbox_docker
```

The default `docker` sandbox backend is not probed during settings composition. Build its fixed
Python 3.14 image before using `sandbox-run` or running reference-aware Scenario decoding; Docker
resources carry `com.tyr.gamr.sandbox=true` labels for orphan diagnosis. Trajectory decoding
invokes the sandbox under process-wide capacity control (`GAMR_MAX_CONCURRENT_DECODERS`, defaulting to 2).
The sandbox runs Python 3.14 with only the standard library, read-only `/input`, ephemeral `/workspace`,
no network access, and strict limits (64 KiB code, 256 files, 64 MiB attachments, 10s execution, 1 MiB output).
Decoder prompts advertise `/input/<opaque-id>/<filename>` and the sandbox receives the corresponding
relative logical attachment path. The decoder reuses one healthy sandbox instance across up to three
tool calls per Scenario Execution. Tool feedback excludes stdout and stderr, identifies the next exact output directory,
and requires derived files for a decoded result. An inspection-only route can be revised to direct
evaluation with its attempt retained. A tool-free non-protocol response is accepted as direct only
when local preparation independently verifies all original uploads as readable. A valid derived text
or image remains usable when an auxiliary
output has an unsupported format; the evidence batch stays incomplete so a negative comparison still
fails closed. Missing approval evidence means approval state is unknown and cannot by itself support
a vulnerable verdict. If decoding fails, the pipeline fails closed to inconclusive. Sensitive reference
data, credentials, and raw tool transcripts are excluded from context and artifacts; the result and
report retain executed source, bounded execution states and streams, route rationale, hashes, and lineage.
Remove only labeled resources owned by the current
GAMR process after an unexpected exit. The Docker backend has no restart policy and never adopts resources
from a previous process.

Use `GAMR_SANDBOX_BACKEND=host-unsafe` only for local controlled snippets. It is not containment:
the child runs with the current user's host permissions. Use `disabled` to keep unrelated GAMR
commands usable on a machine where sandbox execution is not wanted. Decoder workflows in the engine
require contained sandbox isolation and fail safely if sandbox execution is disabled or unsafe.
