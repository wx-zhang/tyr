# Core scope

## Purpose

Own pure Pydantic domain models, JSON contracts, IDs, findings, events, enums, and state transitions.

## Standards

No FastAPI, Typer, filesystem, network, terminal, or vendor SDK imports. Model workflow state explicitly and reject invalid transitions.

## Source map

`tasks.py` owns task documents and template binding; `experiments.py`
owns run/result contracts; `decoding.py` owns bounded route, attempt, execution-stream, and lineage provenance
models; `events.py` owns normalized run activities,
participants, evidence, and transient evidence queries; `workflow.py` owns
discovery candidates, turn decisions, and structured assessments; `states.py`
owns transitions.

Activity and evidence safety tests live in `packages/core/tests/test_events.py`;
browser-facing redaction belongs to the API and adapter tests rather than core.

## Commands

`uv run pytest packages/core/tests` and `uv run python scripts/export_task_schema.py`.
