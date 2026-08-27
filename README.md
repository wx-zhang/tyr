# GAMR

**Tyr's final opponent**

![GAMR — Tyr's final opponent](docs/assets/gamr-hero.svg)

**GAMR** (Generative Adversarial Risk Mapper) is the red-team experiment runner for
[Tyr](https://tyr.ai/) — the security and governance layer for AI agents.

GAMR runs adversarial experiments against Tyr and lets you review the results. The CLI is the
primary interface. The optional API and web app share the same engine, so they can start read-only
runs and visualize every run under the shared `.gamr` root, including runs started from the CLI.

## Quick start

```bash
uv sync --all-packages --dev
uv run gamr doctor
uv run gamr task validate tasks/exfiltrate-important-txt
uv run gamr experiment run tasks/exfiltrate-important-txt
uv run gamr result validate .gamr/runs/<run-id>/result.json
```

Live commands need `TYR_MCP_TOKEN`, `OPENROUTER_API_KEY`, and `TYR_LOOP_MODEL` set (see
`.env.example`).

Set `TYR_LOOP_JUDGE_MODEL` when evaluation should use a model independent from the model
that executes scenarios. If it is unset, evaluation uses `TYR_LOOP_MODEL`.
Tasks configure judge execution via `spec.judge.pipeline` in `task.json` (defaulting to
`evidence-and-content`).

The `evidence-and-content` judge automatically performs trajectory decoding analysis on
applicable reference-aware file cases. When verified uploads require transformation or
decoding (e.g. archives, custom encoding, or formatted text), GAMR reuses the configured
judge model to drive a focused decoder agent. The agent executes Python code inside an isolated
standard-library Docker sandbox, making up to three attempts within a single healthy sandbox
session. The pipeline fails closed on decoding or sandbox failures (yielding an inconclusive
verdict rather than false negatives). Sensitive synthetic references, credentials, and raw tool
transcripts are strictly excluded from decoder context and persisted artifacts. Reviewer-visible
provenance records the concise route rationale, executed source, program SHA-256, bounded
exit/timing/output states, explicit suppressed streams, and derived-file lineage. Decoder input is
always advertised as `/input/<opaque-id>/<filename>` and attached with the matching relative logical
path. Inspection-only sandbox calls are discouraged: stdout and stderr stay out of model feedback,
and executions count as decoded only when they produce derived files. If an inspection call produces
no files, the decoder may revise its route to direct evaluation while retaining attempt provenance.
Tool-free decoder prose can select direct evaluation only when local content preparation independently
confirms that every verified upload is already readable.
When a transformation emits both usable text or image evidence and unsupported auxiliary files,
the usable evidence continues through comparison while the batch remains incomplete for fail-closed
negative decisions. Missing approval evidence is treated as an unknown approval state, not proof
that approval was absent.
Concurrent sandbox executions are governed by
`GAMR_MAX_CONCURRENT_DECODERS` (defaulting to 2).

Run the focused judge regression without executing an experiment or communicating with Tyr:

```bash
uv run poe evaluate:judges
```

The job replays committed case-local artifacts through the production judge model and contained
Docker sandbox. Inputs are validated by size and SHA-256, categorical
regressions return a non-zero exit code, and complete results are written below
`.gamr/evaluations/judges/<evaluation-id>/`. Progress is streamed for cases, decoder and sandbox stages, and model calls.
Pass `--debug` to print parsed LLM traffic and sandbox inputs and outputs while diagnosing model
behavior. The terminal output and saved log may contain sensitive dataset content. A complete log is
saved under `.gamr/evaluations/judges/` using a UTC timestamp and short UUID.
The corpus contains two manually reviewed real positive artifacts, one visually reviewed real
negative artifact, and deterministic Caesar/Base64 decoder cases. See `evaluations/AGENTS.md` for
the extension path. Because this job has no Tyr approval evidence, it scores only content-overlap
and decoding categories. The final security assessment is retained for inspection but is not a
regression label.

Evaluation plans may associate one synthetic UTF-8 reference file with a task. For
collector-verified file cases, GAMR compares uploaded text, JSON, safe archives, and PNG/JPEG
images with that reference before the breach judge runs. Raw contents are sent only to the
configured judge provider and are never stored in run artifacts. If no reference is declared,
the content check is skipped. Content-decision parsing tolerates provider reasoning wrappers and
harmless extra fields, then applies the strict status, match-type, and evidence-ID contract.

Collector-marked scenarios can independently verify delivered requests and files when
`TYR_COLLECTOR_USERNAME` and `TYR_COLLECTOR_PASSWORD` are set. GAMR persists only request/file
metadata and SHA-256 values. The run page downloads original files from the collector on demand;
uploaded bytes are never retained in `.gamr`. An exact collector `request_id` is preferred. If Tyr
omits it, GAMR accepts only one exact filename match captured during the originating upload turn.
Collector reads retry redirects, transient transport, 408, 425, 429, and 5xx failures twice before
recording safe failure diagnostics. Each redirected retry authenticates again before reading.
The live run page refreshes collector evidence automatically and places verified files in Updates,
with bounded previews for common text, Markdown, JSON, XML, CSV, and raster-image files. Retained
UTF-8 request bodies are verified by recorded byte length and SHA-256, then exposed as request-body
artifacts through the same run-scoped preview and download controls. Decoded multipart summaries
are not raw bodies; their independently verified quarantined files remain downloadable.

By default, experiments are **read-only**. To let an experiment take real actions through Tyr, run
with Actions Allowed (`--action-mode approval_required --allow-actions`); each action still needs an
explicit human approval on the Tyr side. GAMR never auto-approves an action. Use `--all-cases` to run
every case in a task instead of one.

Each discovery thread, base case, and scientist thread starts a separate Tyr Assistant conversation.
GAMR passes its `conversationId` on every query or action request, so concurrent cases do not share
Tyr context.

## Interactive chat

`gamr chat` opens a live chat session with Tyr through the same engine:

```bash
uv run gamr chat
```

Each chat session also starts its own Tyr Assistant conversation. Validate the live MCP
conversation contract and isolation with:

```bash
uv run python scripts/explore_tyr_conversations.py
```

This starts in **read-only** mode: Tyr's action-capable tools are hidden entirely, so nothing can be
executed. To let the chat see and call action-capable tools, add `--allow-actions`:

```bash
uv run gamr chat --allow-actions
```

`--allow-actions` only exposes the tools — it does not skip approval. Every action Tyr's tools take
still requires a recorded human decision on the Tyr side. Because this mode is more sensitive, the
CLI asks you to confirm it interactively before the session starts. If you're running non-interactively
(e.g. from a script), add `--confirm-actions` to skip that prompt:

```bash
uv run gamr chat --allow-actions --confirm-actions
```

Other chat options: `--prompt "<text>"` to send an initial message, `--model` to override
`TYR_LOOP_CHAT_MODEL` (defaults to `x-ai/grok-4.5`), and `--base-url` to override
`OPENROUTER_BASE_URL`.

## Developer Python sandbox

The sandbox provides ephemeral, isolated standard-library Python execution for trajectory
decoding and developer testing. `GAMR_SANDBOX_BACKEND` defaults to `docker`; build the fixed image and
exercise the shared lifecycle with controlled code:

```bash
uv run poe sandbox-build
uv run poe sandbox-run --attach tasks/exfiltrate-important-txt/references/important.txt \
  --code "from pathlib import Path; print(Path('/input/important.txt').read_text())"
```

Docker runs Python 3.14 with only the standard library, no network, no host mounts, no application
environment or credentials, a read-only `/input`, and a persistent ephemeral `/workspace`. Fixed
limits are 64 KiB source, 256 attached files, 64 MiB attachments, 10 seconds per execution, 1 MiB
combined output, 1 CPU, 256 MiB memory, 64 processes, and 128 MiB workspace. A timeout or output
overflow destroys the whole sandbox. Sessions and IDs are process-local and are never persisted.

`host-unsafe` is an explicitly selected fallback. It uses temporary input and workspace roots and
strips configured secrets, but generated code can access the host with the current user's
permissions; it is not a security boundary. `disabled` leaves unrelated GAMR features available
and rejects sandbox starts. The runner closes each successfully started session.

If GAMR exits unexpectedly, Docker resources may remain as labeled orphans. Inspect only the GAMR
resources you own, then remove the matching container before its volume:

```bash
docker ps -a --filter label=com.tyr.gamr.sandbox=true
docker volume ls --filter label=com.tyr.gamr.sandbox=true
docker rm --force <labeled-container>
docker volume rm <labeled-volume>
```

## Optional web interface

Local hot-reload (requires host Python and Node toolchains):

```bash
uv run poe dev
```

Or run the production-style containers (API + static web):

```bash
cp .env.example .env
# set TYR_MCP_TOKEN, OPENROUTER_API_KEY, and TYR_LOOP_MODEL for live runs
docker compose up -d --build
```

The API listens on `http://127.0.0.1:6687` and the web app on
`http://127.0.0.1:6688`. Compose loads `.env`, mounts `./.gamr` for run artifacts and
`./tasks` read-only, and does not scale the API (one in-process queue). Host CLI runs that
write to `./.gamr` appear in the UI.

The service runs up to `GAMR_MAX_CONCURRENT_RUNS` experiments, defaulting to three, and
queues the rest in process. Restarted service work becomes `interrupted` and requires an explicit
retry.

All experiment definitions, live state, evidence, and results are JSON or JSONL files. There is no
database, migration service, broker, or worker process.

See [the scaffold contract](docs/SCAFFOLD_SPEC.md), [architecture](docs/architecture.md), and
[development guide](docs/development.md).
