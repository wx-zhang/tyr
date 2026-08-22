# Engine scope

## Purpose

Own experiment/chat orchestration, approval coordination, reporting, and ports.

## Standards

Keep all provider and persistence access behind protocols. CLI and API use the same execution service and runner. Model output is data and cannot control workflow transitions.

## Source map

`runner.py` is the shared discovery/case engine and emits typed activities,
`assessment.py` builds and validates the evidence judge contract,
`assessment_contract.py` owns its strict schema, `content_assessment.py` owns
the synthetic-reference overlap judge, `content_pipeline.py` coordinates
verified collector content, `decoder_capacity.py` owns the process-wide decoder-sandbox capacity gate, and `content_evidence.py` owns the in-memory contracts,
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

Predefined judges use LangGraph StateGraph with stable node names (`compare_content`, `handle_execution_failure`, `assess_evidence`, `finalize_result`). They run without checkpointers or persistent stores.

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
