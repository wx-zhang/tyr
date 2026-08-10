from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from gamr_adapters.artifacts.evidence import FilesystemActivitySink
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.config import Settings
from gamr_adapters.datasets.filesystem import FilesystemDatasetRepository, load_dataset
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_core import (
    ExecutionOutcome,
    ExperimentConfig,
    RunRecord,
    RunResult,
    RunSource,
    RunState,
)
from gamr_core.identifiers import new_id
from gamr_engine import ExecutionOutput, ExperimentExecutionService
from gamr_engine.runner import ProgressEvent
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .composition import build_chat_session
from .progress import render_progress

console = Console()
app = typer.Typer(help="GAMR red-team experiment tools", no_args_is_help=True)
dataset_app = typer.Typer(help="Inspect and validate JSON datasets")
experiment_app = typer.Typer(help="Create and inspect experiment runs")
result_app = typer.Typer(help="Validate canonical run results")
app.add_typer(dataset_app, name="dataset")
app.add_typer(experiment_app, name="experiment")
app.add_typer(result_app, name="result")


def _render_progress(event: ProgressEvent) -> None:
    render_progress(console, event)


@app.command()
def doctor() -> None:
    """Check the local scaffold and safe defaults."""

    checks = {
        "dataset_root": Path("datasets").is_dir(),
        "schema_root": Path("schemas").is_dir(),
        "read_only_default": ExperimentConfig().action_mode == "read_only",
    }
    for name, passed in checks.items():
        console.print(f"[green]OK[/green] {name}" if passed else f"[red]FAIL[/red] {name}")
    if not all(checks.values()):
        raise typer.Exit(code=1)


@dataset_app.command("list")
def list_datasets(root: Path = typer.Option(Path("datasets"), "--root")) -> None:
    """List available dataset manifests."""

    table = Table("ID", "Version", "Title")
    for manifest in FilesystemDatasetRepository(root).list():
        table.add_row(manifest.metadata.id, manifest.metadata.version, manifest.metadata.title)
    console.print(table)


@dataset_app.command("validate")
def validate_dataset(directory: Path) -> None:
    """Validate a dataset manifest and all scenario files."""

    try:
        dataset = load_dataset(directory)
    except Exception as error:
        console.print(f"[red]Invalid dataset:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(
        f"[green]Valid[/green] {dataset.manifest.metadata.id} ({len(dataset.scenarios)} cases)"
    )


@experiment_app.command("run")
def run_experiment(
    directory: Path,
    action_mode: str = typer.Option("read_only", "--action-mode"),
    model: str = typer.Option("", "--model", help="Override GAMR_MODEL_NAME."),
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
    all_cases: bool = typer.Option(False, "--all-cases", help="Run every case in the dataset."),
    scientist_iterations: int = typer.Option(
        0, "--scientist-iterations", min=0, help="Generate and run bounded follow-up scenarios."
    ),
) -> None:
    """Run a dataset through the shared engine and write a JSON bundle."""

    if action_mode not in {"read_only", "approval_required"}:
        raise typer.BadParameter(
            "must be read_only or approval_required", param_hint="--action-mode"
        )
    if allow_actions:
        action_mode = "approval_required"
    if action_mode == "approval_required":
        if not allow_actions:
            raise typer.BadParameter(
                "pass --allow-actions to start an approval_required run",
                param_hint="--allow-actions",
            )
        if not confirm_actions and not sys.stdin.isatty():
            raise typer.BadParameter(
                "non-interactive action runs require --confirm-actions",
                param_hint="--confirm-actions",
            )
        if not confirm_actions and not typer.confirm(
            "Enable action-capable experiment requests? Every Tyr action still requires approval",
            default=False,
        ):
            raise typer.Abort()
    dataset = load_dataset(directory)
    if case_id and all_cases:
        raise typer.BadParameter("use --case-id or --all-cases, not both")
    selected_case_ids = (
        [scenario.metadata.id for scenario in dataset.scenarios] if all_cases else case_id or None
    )
    settings = Settings()
    selected_model = model or settings.model_name
    if not settings.tyr_mcp_token:
        raise typer.BadParameter("GAMR_TYR_MCP_TOKEN is required")
    if not settings.model_api_key:
        raise typer.BadParameter("GAMR_MODEL_API_KEY is required")
    if not selected_model:
        raise typer.BadParameter("GAMR_MODEL_NAME is required")
    artifact_store = FilesystemArtifactStore(
        settings.artifact_root,
        secrets=(settings.tyr_mcp_token, settings.model_api_key),
    )
    target = TyrMcpClient(settings.tyr_mcp_url, settings.tyr_mcp_token)
    model_gateway = OpenAICompatibleModel(
        settings.model_base_url,
        settings.model_api_key,
        selected_model,
    )

    configuration = ExperimentConfig(
        actionMode=action_mode,
        model=selected_model,
        maxTurns=dataset.manifest.spec.defaults.max_turns,
        discoveryTurns=20,
        caseIds=selected_case_ids,
        scientistIterations=scientist_iterations,
    )
    run_id = new_id()
    started_at = datetime.now(UTC)
    run_document = RunRecord(
        id=run_id,
        source=RunSource.CLI,
        dataset=str(directory),
        state=RunState.RUNNING,
        configuration=configuration,
        createdAt=started_at,
        updatedAt=started_at,
    )
    artifact_store.write_json(
        f"runs/{run_id}/run.json",
        run_document.model_dump(by_alias=True, mode="json"),
    )

    async def run_live() -> ExecutionOutput:
        try:
            return await ExperimentExecutionService().execute(
                dataset,
                configuration,
                run_id=run_id,
                target=target,
                model=model_gateway,
                artifacts=artifact_store,
                activity_sink=FilesystemActivitySink(artifact_store),
                progress=_render_progress,
            )
        finally:
            await target.aclose()

    try:
        output = asyncio.run(run_live())
    except (KeyboardInterrupt, asyncio.CancelledError):
        cancelled_at = datetime.now(UTC)
        artifact_store.write_json(
            f"runs/{run_id}/run.json",
            run_document.model_copy(
                update={
                    "state": RunState.CANCELLED,
                    "error_summary": "Cancelled by operator (Ctrl+C)",
                    "updated_at": cancelled_at,
                    "finished_at": cancelled_at,
                }
            ).model_dump(by_alias=True, mode="json"),
        )
        console.print(
            f"[yellow]Cancelled[/] run [cyan]{run_id}[/] [dim]· Ctrl+C[/]"
        )
        raise typer.Exit(code=130) from None
    except Exception as error:
        failed_at = datetime.now(UTC)
        artifact_store.write_json(
            f"runs/{run_id}/run.json",
            run_document.model_copy(
                update={
                    "state": RunState.FAILED,
                    "error_summary": f"{type(error).__name__}: {error}",
                    "updated_at": failed_at,
                    "finished_at": failed_at,
                }
            ).model_dump(by_alias=True, mode="json"),
        )
        raise
    finished_at = datetime.now(UTC)
    terminal_state = (
        RunState.FAILED
        if output.result.outcome
        in {ExecutionOutcome.FAILED, ExecutionOutcome.ERROR, ExecutionOutcome.INTERRUPTED}
        else RunState.CANCELLED
        if output.result.outcome is ExecutionOutcome.CANCELLED
        else RunState.COMPLETED
    )
    artifact_store.write_json(
        f"runs/{run_id}/run.json",
        run_document.model_copy(
            update={
                "state": terminal_state,
                "result_path": "result.json",
                "updated_at": finished_at,
                "finished_at": finished_at,
            }
        ).model_dump(by_alias=True, mode="json"),
    )
    console.print(f"Run [cyan]{output.result.run_id}[/cyan] {terminal_state.value}")
    for result_error in output.result.errors:
        console.print(f"[red]✗[/] {result_error}")
    console.print(output.result_path)


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
    model: str = typer.Option("", "--model", help="Override GAMR_MODEL_NAME."),
    base_url: str = typer.Option("", "--base-url", help="Override GAMR_MODEL_BASE_URL."),
) -> None:
    """Connect to Tyr through a read-only interactive chat session."""

    if allow_actions:
        if not confirm_actions and not sys.stdin.isatty():
            raise typer.BadParameter(
                "non-interactive action chat requires --confirm-actions",
                param_hint="--confirm-actions",
            )
        if not confirm_actions and not typer.confirm(
            "Enable action-capable tools? Each action still requires approval", default=False
        ):
            raise typer.Abort()
    try:
        asyncio.run(
            _chat_loop(
                prompt,
                action_mode="approval_required" if allow_actions else "read_only",
                model=model or None,
                base_url=base_url or None,
            )
        )
    except Exception as error:
        console.print(f"[red]Chat failed:[/red] {type(error).__name__}: {error}")
        raise typer.Exit(code=1) from error


async def _chat_loop(
    initial_prompt: str,
    *,
    action_mode: str,
    model: str | None,
    base_url: str | None,
) -> None:
    async def approve(name: str, arguments: dict[str, object]) -> bool:
        console.print(f"[yellow]Action requested:[/yellow] {name}")
        console.print_json(json.dumps(arguments, ensure_ascii=False, default=str))
        return typer.confirm("Run this tool?", default=False)

    session, target = build_chat_session(
        Settings(),
        action_mode=action_mode,
        approve=approve,
        model_name=model,
        base_url=base_url,
    )
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": (
                "You are a concise command-line assistant connected to Tyr through MCP. "
                "Use available tools for Tyr questions. Never claim a tool succeeded unless "
                "its result says so. If an operation is waiting for input, ask the operator "
                "for the next message."
            ),
        }
    ]
    try:
        tools = await session.connect()
        console.print(f"[green]Connected to Tyr[/green] · {len(tools)} tools · mode={action_mode}")
        next_prompt = initial_prompt
        while True:
            if not next_prompt:
                try:
                    next_prompt = typer.prompt("Message")
                except (EOFError, KeyboardInterrupt):
                    return
            command = next_prompt.strip()
            next_prompt = ""
            if not command:
                continue
            if command in {"/quit", "/exit"}:
                return
            if command == "/help":
                console.print("/help  /tools  /reset  /quit")
                continue
            if command == "/tools":
                console.print("\n".join(tools))
                continue
            if command == "/reset":
                messages = messages[:1]
                console.print("[green]Conversation reset[/green]")
                continue
            answer = await session.run_turn(messages, command)
            console.print(Markdown(answer) if isinstance(answer, str) else answer)
            if initial_prompt:
                return
    finally:
        await target.aclose()
