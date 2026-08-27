from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import typer
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.collector import CollectorClient
from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_adapters.tracing import create_trace_port
from gamr_adapters.tyr.client import TyrMcpClient
from gamr_core import (
    ExecutionOutcome,
    RunRecord,
    RunState,
)
from gamr_engine import ExecutionOutput
from gamr_engine.ports.sandbox import Sandbox
from gamr_engine.ports.tracing import TracePort
from rich.console import Console

from .composition import build_sandbox, configured_secrets


def collector_client(settings: Settings) -> CollectorClient | None:
    username = getattr(settings, "collector_username", "")
    password = getattr(settings, "collector_password", "")
    if not username or not password:
        return None
    return CollectorClient(
        getattr(settings, "collector_base_url", "https://www.tyr.ai/tyrcli/collector"),
        username,
        password,
    )


def validate_action_mode(
    action_mode: str,
    allow_actions: bool,
    confirm_actions: bool,
    prompt_message: str,
) -> str:
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
        if not confirm_actions and not typer.confirm(prompt_message, default=False):
            raise typer.Abort()
    return action_mode


def build_experiment_execution(
    settings: Settings,
    selected_model: str,
    selected_scientist_model: str,
    selected_judge_model: str,
    trace_port: TracePort | None = None,
) -> tuple[
    FilesystemArtifactStore,
    TyrMcpClient,
    CollectorClient | None,
    Sandbox,
    OpenAICompatibleModel,
    OpenAICompatibleModel,
    OpenAICompatibleModel,
]:
    if not settings.tyr_mcp_token:
        raise typer.BadParameter("TYR_MCP_TOKEN is required")
    if not settings.model_api_key:
        raise typer.BadParameter("OPENROUTER_API_KEY is required")
    if not selected_model:
        raise typer.BadParameter("TYR_LOOP_MODEL is required")
    from . import main as main_cli

    store_cls = getattr(main_cli, "FilesystemArtifactStore", FilesystemArtifactStore)
    tyr_cls = getattr(main_cli, "TyrMcpClient", TyrMcpClient)
    model_cls = getattr(main_cli, "OpenAICompatibleModel", OpenAICompatibleModel)
    build_sandbox_fn = getattr(main_cli, "build_sandbox", build_sandbox)
    if trace_port is None:
        trace_port = create_trace_port(settings)

    artifact_store = store_cls(
        settings.artifact_root,
        secrets=configured_secrets(settings),
    )
    collector = collector_client(settings)
    target = tyr_cls(settings.tyr_mcp_url, settings.tyr_mcp_token)
    sandbox = build_sandbox_fn(settings)
    model_gateway = model_cls(
        settings.model_base_url,
        settings.model_api_key,
        selected_model,
        trace_port=trace_port,
    )
    scientist_model_gateway = (
        model_gateway
        if selected_scientist_model == selected_model
        else model_cls(
            settings.model_base_url,
            settings.model_api_key,
            selected_scientist_model,
            trace_port=trace_port,
        )
    )
    judge_model_gateway = (
        model_gateway
        if selected_judge_model == selected_model
        else model_cls(
            settings.model_base_url,
            settings.model_api_key,
            selected_judge_model,
            trace_port=trace_port,
        )
    )
    return (
        artifact_store,
        target,
        collector,
        sandbox,
        model_gateway,
        scientist_model_gateway,
        judge_model_gateway,
    )


def execute_cli_run(
    console: Console,
    run_document: RunRecord,
    artifact_store: FilesystemArtifactStore,
    execute_coro_fn: Callable[[], Coroutine[Any, Any, ExecutionOutput]],
    trace_port: TracePort | None = None,
) -> None:
    run_id = run_document.id
    artifact_store.write_json(
        f"runs/{run_id}/run.json",
        run_document.model_dump(by_alias=True, mode="json"),
    )
    try:
        output = asyncio.run(execute_coro_fn())
    except KeyboardInterrupt, asyncio.CancelledError:
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
        console.print(f"[yellow]Cancelled[/] run [cyan]{run_id}[/] [dim]· Ctrl+C[/]")
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
    finally:
        if trace_port is not None:
            trace_port.flush(timeout=5.0)
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
