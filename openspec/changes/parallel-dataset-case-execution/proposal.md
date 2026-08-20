## Why

Dataset cases currently execute one at a time, which makes multi-case experiments unnecessarily slow even when their work is independent. GAMR needs bounded parallel case execution while preserving isolated Tyr conversations, deterministic results, accurate live evidence, and the serial scientist workflow.

## What Changes

- Execute selected base dataset cases concurrently after discovery, with five concurrent cases by default.
- Let operators configure base-case concurrency from one through five in CLI, API, and web experiment configuration.
- Keep each parallel case's Tyr operation, transcript, progress, and checkpoint state isolated.
- Preserve dataset order in completed results regardless of case completion order.
- Wait for all base cases to finish before starting scientist iterations, which remain serial.
- Represent multiple simultaneously active cases accurately in persisted evidence and run visualization.
- Distinguish not-started, queued, running, assessing, and terminal cases, and derive stage completion from lifecycle progress rather than an intermediate completed activity.
- Replace the flat run-history list with a grouped, expandable history that shows aggregate case progress, keeps the latest activity visible in collapsed summaries, and presents expanded case activity as an oldest-to-newest audit timeline with compact disclosures for completed history.

## Capabilities

### New Capabilities

- `dataset-case-execution`: Bounded parallel execution, isolation, ordering, progress, and scientist-phase coordination for dataset cases.

### Modified Capabilities

None.

## Impact

- The shared engine gains bounded asynchronous base-case scheduling and per-case execution state.
- Experiment configuration and generated schemas gain a `maxConcurrentCases` field constrained to one through five.
- CLI, API, and web experiment surfaces expose the setting.
- Run checkpoints, activity reduction, and visualization must support multiple active cases without exposing operation identifiers or idempotency keys.
- Model, Tyr, collector, and artifact adapters continue to use the shared execution path and must support safe concurrent calls within one run.
- The web run view replaces its single flat update list with a grouped stage and case hierarchy; the oversized run page module must be split into focused components to satisfy the 300-line source limit.
