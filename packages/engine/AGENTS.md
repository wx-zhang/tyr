# Engine scope

## Purpose

Own experiment/chat orchestration, approval coordination, reporting, and ports.

## Standards

Keep all provider and persistence access behind protocols. CLI and API use the same execution service and runner. Model output is data and cannot control workflow transitions.

## Source map

`runner.py` is the shared discovery/case engine and emits typed activities,
`sandbox_preview.py` decorates sandbox ports with append-only, verbatim
operation lifecycle events and logical generation/attempt tracking,
`assessment.py` builds and validates the evidence judge contract,
`assessment_contract.py` owns its strict schema, `content_assessment.py` owns
the synthetic-reference overlap judge, `content_pipeline.py` coordinates
verified collector content, `content_source.py` owns the verified content-source contract and snapshots,
`content_prepare.py` owns shared preparation of original and derived content evidence,
`decoder_capacity.py` owns the process-wide decoder-sandbox capacity gate, and
`content_response.py` normalizes provider framing before strict content-decision validation,
`capacity_sandbox.py` owns decoder capacity sandbox wrapping,
`judge_runtime.py` owns judge runtime construction helpers,
`decoder/` owns trajectory decoding agent, prompt rendering, feedback mapping, execution loop, relative
`/input/<opaque-id>/<filename>` attachment construction, and bounded attempt records; `decoder/executor.py`
owns sandbox stages and lifecycle cleanup, `decoder/output.py` owns derived evidence preparation, and
`decoder/direct.py` validates fallback direct routes, `decoder/records.py` owns safe execution-result records,
and `content_evidence.py` owns the in-memory contracts,
`judges/` contains predefined judge pipelines orchestrated with LangGraph StateGraph:
- `judges/contracts.py`: `JudgeRequest`, `JudgeRuntime`, `JudgeResult`, and `JudgePipeline` protocol
- `judges/registry.py`: immutable registry mapping `JudgePipelineId` to pipeline implementations
- `judges/evidence_and_content/`: `evidence-and-content` StateGraph implementation
`execution.py` finalizes the shared JSON result and report,
`chat.py` is the interactive tool loop, `reporting.py` derives Markdown, and
`ports/` contains provider, artifact, activity-sink, and ephemeral Python sandbox interfaces.

Keep activity emission changes covered in `packages/engine/tests/test_runner.py`;
the CLI and API must continue to consume this same execution path.
Cases waiting for bounded capacity emit `case.queued`; `case.started` is emitted only after a case acquires a slot.

### Judge pipeline conventions

Predefined judges use LangGraph StateGraph with stable node names (`prepare_verified_content`, `decode_trajectory_content`, `compare_reference_content`, `preserve_execution_failure`, `assess_evidence`, `finalize_judgment`). They run without checkpointers or persistent stores. Trajectory decoding reuses the judge model with a standard-library Docker sandbox across up to three attempts per case, fails closed on errors, and is capacity-governed via `DecoderCapacityGate`. Sensitive references and credentials are strictly excluded from decoder execution.
Decoder feedback never exposes stdout or stderr. Executions require derived files, while an inspection-only route may be revised to direct evaluation with its attempt provenance retained.
Usable derived text or images survive unsupported auxiliary outputs, but incomplete evidence cannot support a definitive negative comparison. Missing approval evidence is an unknown approval state, not evidence of an unapproved action.

To add a predefined judge pipeline:
1. Add the pipeline identifier literal in `gamr_core.tasks` (`JudgePipelineId`).
2. Implement the `JudgePipeline` protocol under `gamr_engine/judges/<pipeline_name>/` using a compiled LangGraph `StateGraph`.
3. Register the pipeline in `gamr_engine.judges.registry._REGISTRY`.
4. Add unit and topology tests in `packages/engine/tests/judges/`.
5. Run `uv run poe judge-graph packages/engine/src/gamr_engine/judges/<pipeline_name>` to generate its deterministic graph topology image under `docs/assets/judges/`.

## Commands

`uv run pytest packages/engine/tests` (focused: `uv run pytest packages/engine/tests/judges/`).

## Safety

Read-only defaults and explicit approval are enforced here, not only in delivery adapters.
