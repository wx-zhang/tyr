## Why

GAMR can compare directly readable uploads and safely extracted archives, but it cannot reliably evaluate content transformed through trajectory-specific encodings or ciphers. Scientist-generated scenarios make a fixed transformation catalog insufficient, so GAMR needs an auditable agent that derives reading instructions from the actual Tyr conversation and executes bounded Python before content comparison.

## What Changes

- Add a structured read-plan stage for reference-aware file cases that analyzes the rendered scenario and case trajectory, cites real evidence turns, and explains in natural language how the verified upload should be read.
- Run model-generated Python against collector-verified uploads through a configurable content sandbox, then supply validated derived candidates and their provenance to the existing content-comparison judge.
- Support `GAMR_CONTENT_SANDBOX=docker` as the default backend and explicit `GAMR_CONTENT_SANDBOX=host-unsafe` as an operator-accepted unsafe backend; never fall back from Docker to host execution.
- Keep the read-plan agent and Python runtime blind to synthetic reference content so transformation selection cannot search for a desired match.
- Bound model attempts, execution time, CPU, memory, processes, input and output sizes, logs, candidate count, and persisted diagnostics.
- Preserve directly readable comparison when Python is unnecessary or unavailable, and report an inconclusive comparison when required transformation evidence cannot be prepared.
- Add canonical read-plan and execution provenance to run results, schemas, evidence APIs, and the web case assessment without exposing decoded sensitive content or secret parameters.
- Extend `gamr doctor`, configuration documentation, and development guidance with sandbox availability and the one-time Docker image preparation flow while keeping `uv run poe dev:watch` unchanged.

## Capabilities

### New Capabilities

- `trajectory-guided-content-decoding`: Trajectory analysis, natural-language read plans, bounded Python execution, derived-content provenance, comparison integration, configuration, failure behavior, and operator visibility.

### Modified Capabilities

None.

## Impact

- Core run-result models and generated JSON schemas gain read-plan and sandbox-execution contracts.
- The shared engine gains read-plan orchestration and sandbox ports ahead of content comparison; CLI and API continue to use the same path.
- Model adapters gain a structured read-plan call, while concrete Docker and unsafe host execution remain adapter concerns.
- The Docker backend requires a pinned local sandbox image and a reachable Docker daemon only when Python execution is needed. The initial scope does not mount a Docker socket into the Compose API or add a remote sandbox broker.
- API evidence normalization and generated web types expose redacted read-plan provenance.
- The run interface adds a “How GAMR read this upload” presentation before the sensitive-content comparison.
- Default tests remain offline through fake model, collector, and sandbox ports; live Docker verification remains opt-in.
