# GAMR scaffold specification

Status: accepted
Decision date: 2026-08-09

## Objective

GAMR is a lightweight red-team Experiment runner for Tyr. The CLI is the main interface. An
optional FastAPI service and React app create Experiment Presets, start Experiments, and provide
reviewable Scenario Execution evidence.

## Architecture contract

- One shared engine serves CLI and API execution.
- Apps depend on packages; packages never depend on apps.
- The API calls Python services directly and never invokes CLI subprocesses.
- JSON files are the only persistence layer.
- One API process owns a bounded in-process queue. Distributed coordination is out of scope.
- Read-only remains available. Approval-gated (`approval_required`) runs require explicit operator
  opt-in; GAMR requests actions and Tyr records the human decision for every action.

```text
apps/
  cli/       primary Typer/Rich interface
  api/       optional FastAPI interface and bounded scheduler
  web/       optional React visualization and Experiment launcher
packages/
  core/      domain models, schemas, identifiers, states
  engine/    shared orchestration and execution finalization
  adapters/  JSON files, Tyr, model providers, bundle queries
tasks/       versioned Task JSON with authored Scenarios
schemas/     generated JSON Schema and OpenAPI contracts
```

## Domain identity

An Experiment Preset is saved, reusable configuration. An Experiment is one Task execution attempt.
A Task contains authored Scenarios. Every instantiated Scenario receives a unique Scenario Execution
identity. `scenarioId` identifies the authored Scenario; `scenarioExecutionId` identifies the runtime
occurrence. Completion Outcome describes technical completion. Objective Status describes attacker
progress. Security verdict is a separate assessment.

## Persistence contract

Experiment Presets remain stored at the compatibility path:

```text
.gamr/experiments/<experiment-preset-id>.json
```

Each CLI or service Experiment owns one compatibility bundle:

```text
.gamr/runs/<experiment-id>/
├── run.json
├── task.snapshot.json
├── checkpoint.json
├── checkpoints/
│   ├── scenario-executions/<scenario-execution-id>.json
│   └── cases/<safe-case-id>.json
├── activity.jsonl
├── events.jsonl
├── transcript.jsonl
├── scenario-execution-results/<scenario-execution-id>.json
├── result.json
├── report.md
└── raw/
```

`run.json` remains the storage compatibility token. It records source, optional preset and retry
links, validated configuration, Experiment State, timestamps, result reference, and failure summary.
Existing `.gamr/runs`, `cases/`, `caseId`, scientist artifact roots, and completed bundles remain
readable and are never rewritten by readers. New JSON writes use Scenario terminology.

## Service lifecycle

`POST /api/v1/experiments/{preset-id}/runs` validates an Experiment Preset, writes a queued bundle,
and returns `202`. The API runs up to `GAMR_MAX_CONCURRENT_RUNS` Experiments, default three, and
starts the remainder FIFO. Existing `/api/v1/runs` and `/cases` paths remain compatibility routes.

Cancellation records `cancelled`. Shutdown or startup reconciliation records unfinished
service-owned Experiments as `interrupted`; CLI-owned Experiments are never changed. No work resumes
automatically. Explicit retry creates a linked new Experiment identity and preserves the original
bundle.

## Safety and validation

- Real actions require CLI opt-in and an explicit Tyr-side human decision for every action.
- Evidence is retained verbatim for trusted test operators, including secrets and authorization data.
- Every Tyr request uses an idempotency key.
- Outer Tyr completion never overrides delegated or unsettled work.
- Task, Experiment Preset, Experiment, result, and OpenAPI schemas are generated from owning models.
- Default tests require no live provider and follow risk-weighted TDD.
