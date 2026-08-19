## Context

See `proposal.md` for motivation and `specs/dataset-case-execution/spec.md` for the behavior contract. The engine currently performs discovery, every base case, and the scientist through one runner and one mutable Tyr conversation. Activity and transcript records already carry case IDs, and the visualization contract already exposes plural current case IDs, but the run has one overwrite-style checkpoint and its case-state reducer assumes mostly serial updates. The filesystem bundle remains the source of truth and must keep one process writing each run.

The affected orchestration currently lives in an oversized runner module. This change must use the new concurrency seam to separate related orchestration into focused source files that satisfy the repository's 300-line source-file limit instead of adding more logic to that module.

## Goals / Non-Goals

**Goals:**

- Bound active base-case tasks without limiting discovery or changing scientist iteration semantics.
- Make concurrent case execution independent at the Tyr conversation, transcript, evidence, progress, and checkpoint boundaries.
- Preserve deterministic aggregation and cancellation behavior.
- Keep CLI and API execution on the same engine path.
- Preserve compatibility when reading configurations and bundles created before this field existed.

**Non-Goals:**

- Parallelizing discovery or scientist-generated scenarios.
- Adding a distributed scheduler, process pool, broker, or database.
- Automatically approving actions or weakening per-action Tyr approval.
- Adding dataset-level dependency graphs or resource-lock declarations between cases.
- Resuming interrupted external calls automatically.

## Decisions

### Use bounded asynchronous tasks inside the shared engine

After discovery returns an immutable candidate, the engine creates one task per selected base case under a structured task group. A semaphore initialized from `maxConcurrentCases` bounds active case bodies. Each task writes its `CaseRecord` into a result slot matching the selected dataset order. The task group provides cancellation propagation, while handled case-level failures remain returned case outcomes rather than task exceptions.

This keeps the concurrency decision in the engine and makes CLI and service runs behave identically. A worker queue was considered, but it adds queue lifecycle and result-index bookkeeping without improving a per-run limit of five. Threads and processes were rejected because the workload is asynchronous I/O and they would violate the bundle's single-writer assumption.

### Start each base case with an independent Tyr conversation

Discovery continues through its existing conversation. Every base case receives a new conversation state with no inherited operation identifier or replay prefix. The discovered candidate is supplied through the rendered known-facts block, so a base case does not need to mutate the discovery operation. The initialized target gateway is shared, and the target port's behavioral contract permits concurrent requests that create separate Tyr operations.

Cloning the discovery operation identifier was rejected because simultaneous mutations of one Tyr operation would mix replies and operation continuity. Creating and initializing a separate MCP client per case was rejected as unnecessary connection overhead; it remains a fallback adapter strategy if live Tyr verification shows that one MCP session cannot host independent concurrent operations.

The scientist retains one serial conversation. For normal runs it may continue the discovery conversation, but it never receives a base case's operation or replay state. Resumed scientist runs keep their existing serial discovery and scientist flow.

### Store the concurrency limit in experiment configuration

`ExperimentConfig.max_concurrent_cases`, serialized as `maxConcurrentCases`, defaults to 5 and validates from 1 through 5 inclusive. CLI exposes `--max-concurrent-cases`; API experiment creation and run override DTOs accept the same field; the web form uses a bounded integer control. The value is persisted in experiment records, run records, and results through the existing configuration snapshot.

This is run configuration rather than a dataset default because it controls operator resource use, not scenario meaning. A global environment-only limit was rejected because operators need reproducible per-experiment settings. The hard maximum of five prevents a run configuration from bypassing the agreed resource bound.

### Separate run-level and per-case checkpoint state

The run-level `checkpoint.json` records the current coarse phase and terminal status. During the base-case phase, each case writes atomically to `checkpoints/cases/<safe-case-id>.json`. Discovery and scientist remain serial and may use phase-specific checkpoint files or the run-level checkpoint. Unique case paths prevent overlapping turns from replacing another case's state.

Checkpoint payloads identify the case, phase, turn, pending-call state, and safe operation continuity needed for diagnostics. Existing redaction rules continue to remove idempotency keys, credentials, and configured secrets. No browser endpoint returns protected checkpoint fields. Existing singleton checkpoints remain readable as legacy evidence.

A single map rewritten into `checkpoint.json` was rejected because every case completion would require locked read-modify-write behavior and one damaged update could obscure all active lanes.

### Reduce case state from case-aware activities

The activity log remains the canonical live history. The API reducer seeds selected cases as pending and maps case-scoped events to stable states: pending, active, assessing, completed, failed, blocked, or cancelled. Incidental model, target, and assessment events update the relevant case without falling back to unknown. `currentCaseIds` continues to list every nonterminal active case.

The web case list becomes the primary overview for parallel work and displays each active case's state independently. The combined turn timeline remains chronological and continues to label entries by case ID. Global waiting or working indicators must not imply that only one case is active; when necessary they are replaced or supplemented by per-case busy states.

### Preserve deterministic scientist history and results

Concurrent completion order affects activity sequence and timestamps only. Base `CaseRecord` and `CaseResult` collections are reconstructed in selected dataset order before summary calculation, result writing, reporting, and scientist history construction. Scientist generation starts only after the task group exits successfully and then proceeds one iteration at a time.

Sorting terminal results by completion time was rejected because it would make repeated runs nondeterministic and would change the manifest-order contract used by history and reporting.

### Keep concurrency safe across adapters

The model, Tyr, and collector adapters use their existing asynchronous clients. Concurrent calls may share those clients, but no mutable case conversation state lives in an adapter singleton. Artifact JSONL appends and activity sequence assignment remain synchronous operations on the event-loop thread; per-case checkpoint and result artifacts use unique atomic paths. Tests will verify unique, monotonic activity sequences and parseable JSONL under deliberately interleaved cases.

## Risks / Trade-offs

- [Tyr may serialize or reject concurrent operations within one MCP session] → Add an opt-in live integration check for independent operations and retain a gateway-pool fallback without changing the engine contract.
- [Parallel action-enabled cases can present several approvals and mutate the same remote workspace concurrently] → Keep the limit at five, display every active case, preserve independent approvals, and document that datasets are responsible for using non-conflicting artifact names.
- [Shared provider rate limits may increase transient failures] → Bound concurrency at five and preserve existing retry and case-level error behavior; operators can select a lower value down to one.
- [Interleaved evidence is harder to read] → Retain global chronological sequence while attaching case IDs to every case-scoped record and showing per-case state in the overview.
- [An unexpected task exception cancels sibling work] → Treat expected provider and assessment failures as case results; reserve structured cancellation for invariant violations and explicit run cancellation.
- [Old binaries reject new persisted configuration fields because models forbid extras] → Avoid eager rewrites and use the migration and rollback sequence below.

## Migration Plan

1. Add the optional-defaulted configuration field and reader compatibility before any surface writes it.
2. Add engine scheduling, isolated conversations, per-case checkpoints, and concurrent evidence tests.
3. Add API and CLI surfaces, regenerate JSON and OpenAPI schemas, then add the web control and regenerated client.
4. Update run visualization and documentation before enabling the new default in released entry points.
5. Validate old fixtures without `maxConcurrentCases`; they resolve to the default value of 5 without rewriting canonical bundles.

Rollback must use a compatibility build that accepts and ignores `maxConcurrentCases` before deploying an older binary. Completed run bundles remain immutable; mutable experiment and unfinished run documents must not be rewritten solely for rollback.
