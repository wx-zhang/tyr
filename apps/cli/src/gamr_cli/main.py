from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from gamr_adapters.config import Settings
from gamr_adapters.tasks.filesystem import FilesystemTaskRepository, load_task
from gamr_core import ExperimentPresetConfig, ExperimentResult
from gamr_engine.experiments.records import ProgressEvent
from rich.console import Console
from rich.table import Table

from .chat_cli import run_chat_loop
from .composition import configured_secrets
from .evaluation_cli import run_judge_evaluation_command
from .experiment_commands import experiment_app
from .progress import render_progress
from .runner_cli import (
    validate_action_mode,
)

console = Console()
app = typer.Typer(
    help="GAMR — Tyr's final opponent. Red-team experiment tools for Tyr (https://tyr.ai/).",
    no_args_is_help=True,
)
task_app = typer.Typer(help="Inspect and validate JSON tasks")
result_app = typer.Typer(help="Validate canonical experiment results")
evaluate_app = typer.Typer(help="Run focused live regression evaluations")

app.add_typer(task_app, name="task")
app.add_typer(experiment_app, name="experiment")
app.add_typer(result_app, name="result")
app.add_typer(evaluate_app, name="evaluate")


def _configured_secrets(settings: Settings) -> tuple[str, ...]:
    return configured_secrets(settings)


def _render_progress(event: ProgressEvent) -> None:
    render_progress(console, event)


@app.command()
def doctor() -> None:
    """Check the local scaffold and safe defaults."""

    checks = {
        "task_root": Path("tasks").is_dir(),
        "schema_root": Path("schemas").is_dir(),
        "read_only_default": ExperimentPresetConfig().action_mode == "read_only",
    }
    for name, passed in checks.items():
        console.print(f"[green]OK[/green] {name}" if passed else f"[red]FAIL[/red] {name}")
    if not all(checks.values()):
        raise typer.Exit(code=1)


@task_app.command("list")
def list_tasks(root: Path = typer.Option(Path("tasks"), "--root")) -> None:
    """List available task manifests."""

    table = Table("ID", "Version", "Title")
    for manifest in FilesystemTaskRepository(root).list():
        table.add_row(manifest.metadata.id, manifest.metadata.version, manifest.metadata.title)
    console.print(table)


@task_app.command("validate")
def validate_task(directory: Path) -> None:
    """Validate a task manifest and all scenario files."""

    try:
        task = load_task(directory)
    except Exception as error:
        console.print(f"[red]Invalid task:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(
        f"[green]Valid[/green] {task.manifest.metadata.id} ({len(task.scenarios)} Scenarios)"
    )


@result_app.command("validate")
def validate_result(path: Path) -> None:
    """Validate a canonical Experiment result JSON file."""

    try:
        ExperimentResult.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as error:
        console.print(f"[red]Invalid result:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Valid result[/green] {path}")


@evaluate_app.command("judges")
def evaluate_judges(
    dataset: Path = typer.Option(
        Path("evaluations/judges/evidence-and-content/dataset.json"),
        "--dataset",
    ),
    model: str = typer.Option("", "--model", help="Override TYR_LOOP_JUDGE_MODEL."),
    case_id: list[str] = typer.Option([], "--case-id", help="Select a dataset case."),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Print and save complete LLM and sandbox inputs and outputs.",
    ),
) -> None:
    """Replay committed evidence through a production judge pipeline."""

    try:
        run_judge_evaluation_command(console, dataset, model, case_id, debug)
    except typer.Exit:
        raise
    except Exception as error:
        console.print(f"[red]Judge evaluation failed:[/red] {type(error).__name__}: {error}")
        raise typer.Exit(code=1) from error


@app.command()
def chat(
    prompt: str = typer.Option("", "--prompt"),
    approval_gated: bool = typer.Option(
        False,
        "--approval-gated",
        "--allow-actions",
        help="Use Approval-gated mode; Tyr requires a human decision for every action.",
    ),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm Approval-gated chat without an interactive prompt.",
    ),
    model: str = typer.Option("", "--model", help="Override GAMR_CHAT_MODEL_NAME."),
    base_url: str = typer.Option("", "--base-url", help="Override OPENROUTER_BASE_URL."),
) -> None:
    """Connect to Tyr through a read-only interactive chat session."""

    action_mode = validate_action_mode(
        "approval_required" if approval_gated else "read_only",
        approval_gated,
        confirm_actions,
        "Use Approval-gated tools? Tyr requires an explicit human decision for every action",
    )
    try:
        asyncio.run(
            run_chat_loop(
                console,
                prompt,
                action_mode=action_mode,
                model=model or None,
                base_url=base_url or None,
            )
        )
    except Exception as error:
        console.print(f"[red]Chat failed:[/red] {type(error).__name__}: {error}")
        raise typer.Exit(code=1) from error
