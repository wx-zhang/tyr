# Engine scope

## Purpose

Own experiment/chat orchestration, approval coordination, reporting, and ports.

## Standards

Keep all provider and persistence access behind protocols. CLI and API use the same execution service and runner. Model output is data and cannot control workflow transitions.

## Source map

`runner.py` is the shared discovery/case engine and emits typed activities,
`execution.py` finalizes the shared JSON result and report,
`chat.py` is the interactive tool loop, `reporting.py` derives Markdown, and
`ports/` contains provider, artifact, and activity-sink interfaces.

Keep activity emission changes covered in `packages/engine/tests/test_runner.py`;
the CLI and API must continue to consume this same execution path.

## Commands

`uv run pytest packages/engine/tests`.

## Safety

Read-only defaults and explicit approval are enforced here, not only in delivery adapters.
