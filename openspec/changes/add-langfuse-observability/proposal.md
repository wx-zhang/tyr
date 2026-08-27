## Why

GAMR retains canonical run evidence locally but lacks searchable, hierarchical observability across model calls, cases, scientist retries, chat turns, and judge evaluations. An opt-in local Langfuse projection will make latency, usage, prompts, responses, and outcomes inspectable without changing execution semantics or making an external service authoritative.

## What Changes

- Add explicitly enabled Langfuse tracing for every GAMR model workflow while preserving the existing model gateway and direct OpenAI-compatible integration.
- Represent experiments as run traces with nested case or phase spans and model generations; group base runs and scientist resumes by source-run lineage.
- Represent chat conversations and judge evaluation invocations with stable session and trace correlation.
- Store verbatim model inputs and outputs in the trusted local Langfuse deployment and publish case-level and run-level categorical scores from existing GAMR results.
- Make tracing best-effort: initialization, export, and flush failures never alter a GAMR result, while local diagnostics expose tracing failures.
- Require `GAMR_LANGFUSE_ENABLED=true`; configured credentials alone never enable export.
- Support both an externally managed local Langfuse endpoint and an optional loopback-only Docker Compose profile with manually retained data.
- Keep `.gamr` run bundles and source-controlled prompts canonical. Do not add Langfuse prompt management or migrate to LangChain.

## Capabilities

### New Capabilities

- `langfuse-observability`: Opt-in local tracing, correlation, score projection, failure isolation, trusted-data handling, and deployment behavior for all GAMR model workflows.

### Modified Capabilities

None.

## Impact

- Adds a Langfuse SDK dependency to `gamr-adapters` and a vendor-neutral optional tracing boundary to `gamr-engine`.
- Updates CLI and API composition, lifecycle flushing, model workflow instrumentation, configuration, tests, environment documentation, and Docker Compose services.
- Adds local Langfuse operational volumes containing trusted-operator evidence; these volumes are not canonical artifacts and have manual retention.
- Does not change task or run-result schemas, model-provider behavior, Tyr approval rules, sandbox behavior, prompt ownership, or existing execution outcomes.
