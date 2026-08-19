# GAMR scaffold specification

Status: accepted
Decision date: 2026-08-09

## Objective

GAMR is a lightweight red-team experiment runner for Tyr. The CLI is the main interface. An
optional FastAPI service and React app provide experiment starts and visualization.

## Architecture contract

- One shared engine serves CLI and API execution.
- Apps depend on packages; packages never depend on apps.
- The API calls Python services directly and never invokes CLI subprocesses.
- JSON files are the only persistence layer.
- One API process owns a bounded in-process queue. Distributed coordination is out of scope.
- Read-only remains available. Action-enabled (`approval_required`) service runs require explicit operator opt-in; GAMR never auto-approves Tyr actions.

```text
apps/
  cli/       primary Typer/Rich interface
  api/       optional FastAPI interface and bounded scheduler
  web/       optional React visualization and experiment launcher
packages/
  core/      domain models, schemas, identifiers, states
  engine/    shared orchestration and execution finalization
  adapters/  JSON files, Tyr, model providers, bundle queries
tasks/       versioned task JSON
schemas/     generated JSON Schema and OpenAPI contracts
```

## Persistence contract

Reusable experiments are atomic JSON documents:

```text
.gamr/experiments/<experiment-id>.json
```

Each CLI or service run owns one bundle:

```text
.gamr/runs/<run-id>/
├── run.json
├── task.snapshot.json
├── checkpoint.json
├── activity.jsonl
├── events.jsonl
├── transcript.jsonl
├── result.json
├── report.md
└── raw/
```

`run.json` records source (`cli` or `service`), optional experiment and retry links, validated
configuration, lifecycle state, timestamps, result reference, and redacted failure summary.
Mutable JSON documents use atomic replacement. JSONL has one writer per run. Readers may tolerate
an incomplete trailing record only while a run is live.

CLI and API use the same configured artifact root. API discovery does not register or rewrite CLI
runs. Completed bundles remain evaluable without any service.

## Service lifecycle

`POST /api/v1/experiments/{id}/runs` validates the experiment, writes a queued bundle, and
returns `202`. The API runs up to `GAMR_MAX_CONCURRENT_RUNS` experiments, default three, and starts
the remainder FIFO.

Cancellation records `cancelled`. Shutdown or startup reconciliation records unfinished
service-owned runs as `interrupted`; CLI-owned runs are never changed. No work resumes or replays
automatically. Explicit retry creates a linked new run ID and preserves the original bundle.

Run lists, SSE, visualization, activity filters, relationships, evidence, cases, and artifacts are
derived from the bundle. Relationship tokens and cursors stay run-scoped and bounded.

## Safety and validation

- Real actions require CLI opt-in and a recorded human decision for every Tyr action.
- Secrets are redacted before persistence or browser delivery.
- Every Tyr request uses an idempotency key.
- Outer Tyr completion never overrides delegated or unsettled work.
- Task, experiment, live-run, result, and OpenAPI schemas are generated from owning models.
- Default tests require no live provider and follow risk-weighted TDD.

## Extension policy

Do not add a database, broker, worker, distributed lock, or network filesystem abstraction without
a demonstrated deployment requirement. A future store or coordinator replaces the adapter or API
scheduler seam; it does not fork engine behavior.
