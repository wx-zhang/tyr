from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from gamr_adapters.config import Settings
from gamr_adapters.tasks.filesystem import FilesystemTaskRepository, load_task
from gamr_core import (
    ExperimentConfig,
    RunResult,
)
from gamr_engine.runner import ProgressEvent
from rich.console import Console
from rich.table import Table

from .chat_cli import run_chat_loop
from .composition import configured_secrets
from .evaluation_cli import run_judge_evaluation_command
from .experiment_cli import (
    resume_scientist_command,
    run_experiment_command,
)
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
experiment_app = typer.Typer(help="Create and inspect experiment runs")
result_app = typer.Typer(help="Validate canonical run results")
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
        "read_only_default": ExperimentConfig().action_mode == "read_only",
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
    console.print(f"[green]Valid[/green] {task.manifest.metadata.id} ({len(task.scenarios)} cases)")


@experiment_app.command("run")
def run_experiment(
    directory: Path,
    action_mode: str = typer.Option("read_only", "--action-mode"),
    model: str = typer.Option("", "--model", help="Override TYR_LOOP_MODEL."),
    scientist_model: str = typer.Option(
        "", "--scientist-model", help="Override TYR_LOOP_SCIENTIST_MODEL."
    ),
    judge_model: str = typer.Option("", "--judge-model", help="Override TYR_LOOP_JUDGE_MODEL."),
    allow_actions: bool = typer.Option(
        False,
        "--allow-actions",
        help="Enable approval_required mode for a live run.",
    ),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm an action-enabled run without an interactive prompt.",
    ),
    case_id: list[str] = typer.Option(
        [], "--case-id", help="Select a case; repeat to run multiple cases in manifest order."
    ),
    all_cases: bool = typer.Option(False, "--all-cases", help="Run every case in the task."),
    max_concurrent_cases: int = typer.Option(
        5,
        "--max-concurrent-cases",
        min=1,
        max=5,
        help="Maximum concurrent base cases to run.",
    ),
    scientist_iterations: int = typer.Option(
        0, "--scientist-iterations", min=0, help="Generate and run bounded follow-up scenarios."
    ),
    history_test_runs: int = typer.Option(
        10,
        "--history-test-runs",
        min=0,
        max=100,
        help="Use this many latest unique base scenarios as history.",
    ),
    history_scientist_runs: int = typer.Option(
        5,
        "--history-scientist-runs",
        min=0,
        max=100,
        help="Use this many latest unique scientist scenarios as history.",
    ),
) -> None:
    """Run a task through the shared engine and write a JSON bundle."""

    run_experiment_command(
        console=console,
        directory=directory,
        action_mode=action_mode,
        model=model,
        scientist_model=scientist_model,
        judge_model=judge_model,
        allow_actions=allow_actions,
        confirm_actions=confirm_actions,
        case_id=case_id,
        all_cases=all_cases,
        max_concurrent_cases=max_concurrent_cases,
        scientist_iterations=scientist_iterations,
        history_test_runs=history_test_runs,
        history_scientist_runs=history_scientist_runs,
        render_progress_cb=_render_progress,
    )


@experiment_app.command("resume-scientist")
def resume_scientist_experiment(
    run_id: str,
    scientist_iterations: int = typer.Option(
        0,
        "--scientist-iterations",
        min=0,
        help="Override the source run's scientist_iterations.",
    ),
    model: str = typer.Option("", "--model", help="Override TYR_LOOP_MODEL."),
    scientist_model: str = typer.Option(
        "", "--scientist-model", help="Override TYR_LOOP_SCIENTIST_MODEL."
    ),
    judge_model: str = typer.Option("", "--judge-model", help="Override TYR_LOOP_JUDGE_MODEL."),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm an action-enabled resume without an interactive prompt.",
    ),
) -> None:
    """Resume only the scientist phase of a prior run, seeded with its case history."""

    resume_scientist_command(
        console=console,
        run_id=run_id,
        scientist_iterations=scientist_iterations,
        model=model,
        scientist_model=scientist_model,
        judge_model=judge_model,
        confirm_actions=confirm_actions,
        render_progress_cb=_render_progress,
    )


@experiment_app.command("show")
def show_experiment(run_id: str) -> None:
    """Show a stored run result."""

    path = Path(".gamr") / "runs" / run_id / "result.json"
    if not path.exists():
        raise typer.BadParameter(f"run does not exist: {run_id}")
    console.print_json(path.read_text(encoding="utf-8"))


@result_app.command("validate")
def validate_result(path: Path) -> None:
    """Validate a canonical result JSON file."""

    try:
        RunResult.model_validate_json(path.read_text(encoding="utf-8"))
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
    allow_actions: bool = typer.Option(
        False,
        "--allow-actions",
        help="Expose action-capable Tyr tools; every call still requires approval.",
    ),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm action-capable chat without an interactive prompt.",
    ),
    model: str = typer.Option("", "--model", help="Override TYR_LOOP_CHAT_MODEL."),
    base_url: str = typer.Option("", "--base-url", help="Override OPENROUTER_BASE_URL."),
) -> None:
    """Connect to Tyr through a read-only interactive chat session."""

    action_mode = validate_action_mode(
        "approval_required" if allow_actions else "read_only",
        allow_actions,
        confirm_actions,
        "Enable action-capable tools? Each action still requires approval",
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
