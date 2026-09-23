# Core scope

## Purpose

Own pure Pydantic domain models, JSON contracts, IDs, findings, events, enums, and state transitions.

## Standards

No FastAPI, Typer, filesystem, network, terminal, or vendor SDK imports. Model workflow state explicitly and reject invalid transitions.

## Source map

`benign.py` owns independent functional scenario, batch submission, run and assessment
contracts. It does not reuse adversarial outcomes.

`tasks.py` owns task documents and template binding; `experiments.py`
owns run/result contracts; `decoding.py` owns bounded route, attempt, execution-stream, and lineage provenance
models; `sandbox.py` owns pipeline-neutral sandbox operation states, bounded
preview text, execution results, attempts, and folded session contracts;
`events.py` owns normalized run activities,
participants, evidence, and transient evidence queries; `workflow.py` owns
discovery candidates, turn decisions, and structured assessments; `states.py`
owns transitions.

Activity and evidence safety tests live in `packages/core/tests/test_events.py`;
evidence models preserve supplied values; access control belongs to the API.

## Commands

`uv run pytest packages/core/tests` and `uv run python scripts/export_task_schema.py`.
