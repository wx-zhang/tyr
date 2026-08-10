# Schema scope

## Purpose

Own generated JSON Schema and OpenAPI artifacts.

## Standards

- `dataset.schema.json` is exported from `gamr-core`.
- `run-result.schema.json` is exported from `gamr-core`.
- `experiment.schema.json` and `run.schema.json` validate filesystem operational records.
- `openapi.json` is exported from `gamr-api`.
- Regenerate with `uv run poe schemas`; do not hand-edit generated files.

## Verification

Check generated files for drift in CI with `uv run poe check`.
