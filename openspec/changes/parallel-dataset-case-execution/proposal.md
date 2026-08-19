## Why

Dataset cases currently execute one at a time, which makes multi-case experiments unnecessarily slow even when their work is independent. GAMR needs bounded parallel case execution while preserving isolated Tyr conversations, deterministic results, accurate live evidence, and the serial scientist workflow.

## What Changes

- Execute selected base dataset cases concurrently after discovery, with five concurrent cases by default.
- Let operators configure base-case concurrency from one through five in CLI, API, and web experiment configuration.
- Keep each parallel case's Tyr operation, transcript, progress, and checkpoint state isolated.
- Preserve dataset order in completed results regardless of case completion order.
- Wait for all base cases to finish before starting scientist iterations, which remain serial.
- Represent multiple simultaneously active cases accurately in persisted evidence and run visualization.

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
