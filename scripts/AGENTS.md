# Script scope

## Purpose

Own deterministic schema export and local seed utilities.

## Standards

Scripts must be importable, fail clearly, avoid network calls, and write only their documented generated targets.

`export_operational_schemas.py` exports the JSON-only experiment and live-run contracts.
`render_judge_graph.py` provides offline, deterministic PIL-based topology rendering for registered judge pipelines via `uv run poe judge-graph <judge-directory>`, writing PNG images to `docs/assets/judges/`.
`sandbox_run.py` exercises the shared sandbox lifecycle via `uv run poe sandbox-run`.
`sandbox_build.py` builds the fixed sandbox image via `uv run poe sandbox-build` with a confined adapter-package context.
