# Adapter scope

## Purpose

Own Tyr MCP, model, task JSON, run-bundle, query, and artifact implementations.

## Standards

External I/O is async where practical. Redact credentials before persistence. Tyr operation settling remains distinct from outer terminal status, and artifact paths stay below the configured root.

## Source map

`tyr/` owns MCP transport and settling, `models/` owns OpenAI-compatible
providers and recovers a JSON object from `reasoning`/`reasoning_content` when
`content` is empty, `tasks/` owns confined Task and Scenario loading, and `artifacts/` owns
verbatim Experiment bundles, atomic Experiment-level and per-Scenario Execution checkpoint
operations (`checkpoints/cases/<scenario-execution-id>.json` is the historical path),
canonical activity writes, and legacy normalization.
`collector.py` owns authenticated exact and timestamp/filename collector lookup,
bounded retries, and digest-verified file, snapshot, and retained request-body downloads;
`collector_content.py` prepares bounded text, image, and safe archive content
via the shared engine preparation service without writing an artifact copy;
`collector_html.py` parses the admin HTML without retaining credentials or headers.
`artifacts/redaction.py` is a compatibility pass-through. Decoding provenance preserves route rationale,
source, hashes, bounded execution states, failure stage, streams, lineage, and transient identities,
including sensitive values. It applies the same bounded preview rules to
generic sandbox events. `artifacts/evidence.py` folds interleaved sandbox event
deltas into one Scenario Execution-owned operation turn. `artifacts/query.py` owns bounded
in-memory activity and relationship projections derived from bundles.
`artifacts/scientist_scenarios.py` owns the confined cross-Experiment Adversarial Researcher
Scenario catalog, exact JSON exports, and per-occurrence archive markers;
marker state is operational and never rewrites Experiment evidence.
`tracing.py` owns the Langfuse trace port adapter (`LangfuseTracePort`) and `create_trace_port` factory; `tracing_diagnostics.py` owns `DiagnosticReporter`; `tracing_observation.py` owns `LangfuseObservation`; traces contain verbatim evidence and local Langfuse storage is trusted-operator data.

`config.py` loads and validates configuration settings including `GAMR_MAX_CONCURRENT_DECODERS`,
`GAMR_ADVERSARIAL_RESEARCHER_OUTPUT_TOKENS`, and Langfuse observability settings
(`is_langfuse_valid`).
`sandbox/` owns attachment snapshots, output collection (`collect_output.py`),

the disabled and explicitly unsafe host backends, the fixed Docker CLI backend,
its Python 3.14 image, and bounded process support.

Canonical artifact, scientist-catalog, and configured-secret regressions live in
`packages/adapters/tests/test_artifacts.py` and
`packages/adapters/tests/test_scientist_scenarios.py`; normalization, projection
recovery, relationship, and history behavior remain in the neighboring evidence tests.

## Commands

`uv run pytest packages/adapters/tests` (Docker runtime checks: `uv run pytest -m sandbox_docker`).
