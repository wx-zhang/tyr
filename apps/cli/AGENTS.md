# CLI scope

## Purpose

Own the installed `gamr` Typer command and Rich terminal presentation.

The source entrypoint is `src/gamr_cli/main.py`; `src/gamr_cli/progress.py`
renders live Experiment progress, including Tyr request and reply message bodies
as terminal Markdown. `src/gamr_cli/experiment_commands.py` owns the three
Experiment Typer declarations and their `--log-llm [default|thinking]` option.
`src/gamr_cli/experiment_cli.py` handles Experiment execution and Adversarial
Researcher resume commands. `src/gamr_cli/llm_logging.py` owns the console-only
provider reasoning renderer. `src/gamr_cli/runner_cli.py` and
`src/gamr_cli/composition.py` own execution composition, global decoder capacity
gating (`GAMR_MAX_CONCURRENT_DECODERS`), Adversarial Researcher completion limits
(`GAMR_ADVERSARIAL_RESEARCHER_OUTPUT_TOKENS`), and Scenario Execution concurrency.
Ctrl+C during `experiment run` cancels the Experiment and persists `cancelled`
on the Experiment record (exit code 130).
`src/gamr_cli/evaluation_cli.py` composes opt-in live judge evaluations;
`src/gamr_cli/judge_evaluation*.py` loads verified local Scenario collections, runs registered
pipelines, records safe model traces, and applies categorical expectations without contacting Tyr.

## Standards

Commands compose shared engine services and must not implement experiment algorithms. Keep non-interactive commands scriptable and return non-zero on validation errors.

## Commands

`uv run gamr --help`, `uv run gamr doctor`, `uv run poe evaluate:judges`, and
`pytest apps/cli/tests`.

## Safety

Read-only is the default. Interactive approvals must show the tool and normalized arguments; never auto-approve.
