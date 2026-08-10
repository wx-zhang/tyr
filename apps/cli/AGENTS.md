# CLI scope

## Purpose

Own the installed `gamr` Typer command and Rich terminal presentation.

The source entrypoint is `src/gamr_cli/main.py`; `src/gamr_cli/progress.py`
renders live experiment progress, including Tyr request and reply message bodies
as terminal Markdown. Ctrl+C during `experiment run` cancels the run and
persists `cancelled` on the run record (exit code 130).

## Standards

Commands compose shared engine services and must not implement experiment algorithms. Keep non-interactive commands scriptable and return non-zero on validation errors.

## Commands

`uv run gamr --help`, `uv run gamr doctor`, and `pytest apps/cli/tests`.

## Safety

Read-only is the default. Interactive approvals must show the tool and normalized arguments; never auto-approve.
