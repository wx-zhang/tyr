from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from gamr_adapters.artifacts.evidence import FilesystemActivitySink
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.config import Settings
from gamr_adapters.tasks.filesystem import load_task, resolve_task_directory
from gamr_adapters.tracing import create_trace_port
from gamr_core import (
    ExperimentConfig,
    RunRecord,
    RunSource,
    RunState,
)
from gamr_core.identifiers import new_id
from gamr_engine import ExecutionOutput, ExperimentExecutionService
from rich.console import Console

from .composition import configured_secrets
from .runner_cli import (
    build_experiment_execution,
    execute_cli_run,
    validate_action_mode,
)

experiment_app = typer.Typer(help="Create and inspect experiment runs")


def run_experiment_command(
    console: Console,
    directory: Path,
    action_mode: str,
    model: str,
    scientist_model: str,
    judge_model: str,
    allow_actions: bool,
    confirm_actions: bool,
    case_id: list[str],
    all_cases: bool,
    max_concurrent_cases: int,
    scientist_iterations: int,
    history_test_runs: int,
    history_scientist_runs: int,
    render_progress_cb: Any,
) -> None:
    from . import main as main_cli

    action_mode = validate_action_mode(
        action_mode,
        allow_actions,
        confirm_actions,
        "Enable action-capable experiment requests? Every Tyr action still requires approval",
    )
    load_fn = getattr(main_cli, "load_task", load_task)
    task = load_fn(directory)
    if case_id and all_cases:
        raise typer.BadParameter("use --case-id or --all-cases, not both")
    selected_case_ids = (
        [scenario.metadata.id for scenario in task.scenarios] if all_cases else case_id or None
    )

    settings_cls = getattr(main_cli, "Settings", Settings)
    settings = settings_cls()
    selected_model = model or settings.model_name
    selected_scientist_model = scientist_model or settings.scientist_model_name or selected_model
    selected_judge_model = (
        judge_model or getattr(settings, "judge_model_name", "") or selected_model
    )
    trace_port = getattr(settings, "trace_port", None) or getattr(
        main_cli, "create_trace_port", create_trace_port
    )(settings)
    build_fn = getattr(main_cli, "build_experiment_execution", build_experiment_execution)
    try:
        (
            artifact_store,
            target,
            collector,
            sandbox,
            model_gateway,
            scientist_model_gateway,
            judge_model_gateway,
        ) = build_fn(
            settings,
            selected_model,
            selected_scientist_model,
            selected_judge_model,
            trace_port=trace_port,
        )
    except TypeError:
        (
            artifact_store,
            target,
            collector,
            sandbox,
            model_gateway,
            scientist_model_gateway,
            judge_model_gateway,
        ) = build_fn(settings, selected_model, selected_scientist_model, selected_judge_model)

    configuration = ExperimentConfig(
        actionMode=action_mode,
        model=selected_model,
        scientistModel=selected_scientist_model,
        judgeModel=selected_judge_model,
        maxTurns=task.manifest.spec.defaults.max_turns,
        discoveryTurns=20,
        caseIds=selected_case_ids,
        maxConcurrentCases=max_concurrent_cases,
        scientistIterations=scientist_iterations,
        historyTestRuns=history_test_runs,
        historyScientistRuns=history_scientist_runs,
    )
    run_id = new_id()
    started_at = datetime.now(UTC)
    run_document = RunRecord(
        id=run_id,
        source=RunSource.CLI,
        task=str(directory),
        state=RunState.RUNNING,
        configuration=configuration,
        createdAt=started_at,
        updatedAt=started_at,
    )

    async def run_live() -> ExecutionOutput:
        try:
            sink_cls = getattr(main_cli, "FilesystemActivitySink", FilesystemActivitySink)
            return await ExperimentExecutionService().execute(
                task,
                configuration,
                run_id=run_id,
                target=target,
                model=model_gateway,
                scientist_model=scientist_model_gateway,
                judge_model=judge_model_gateway,
                artifacts=artifact_store,
                activity_sink=sink_cls(artifact_store),
                progress=render_progress_cb,
                delivery_verifier=collector,
                content_evidence_provider=collector,
                sandbox=sandbox,
                scientist_output_tokens=settings.scientist_output_tokens,
                trace_port=trace_port,
            )
        finally:
            await target.aclose()
            if collector is not None:
                await collector.aclose()

    execute_cli_run(console, run_document, artifact_store, run_live, trace_port=trace_port)


def resume_scientist_command(
    console: Console,
    run_id: str,
    scientist_iterations: int,
    model: str,
    scientist_model: str,
    judge_model: str,
    confirm_actions: bool,
    render_progress_cb: Any,
) -> None:
    from . import main as main_cli

    settings = getattr(main_cli, "Settings", Settings)()
    artifact_store = FilesystemArtifactStore(
        settings.artifact_root,
        secrets=configured_secrets(settings),
    )
    try:
        source_record = RunRecord.model_validate(artifact_store.read_json(run_id, "run.json"))
    except FileNotFoundError:
        raise typer.BadParameter(f"run does not exist: {run_id}", param_hint="run_id") from None

    configuration = source_record.configuration
    if scientist_iterations:
        configuration = configuration.model_copy(
            update={"scientist_iterations": scientist_iterations}
        )
    if not configuration.scientist_iterations:
        raise typer.BadParameter(
            "source run has scientist_iterations=0; pass --scientist-iterations",
            param_hint="--scientist-iterations",
        )
    if configuration.action_mode == "approval_required":
        if not confirm_actions and not sys.stdin.isatty():
            raise typer.BadParameter(
                "non-interactive action runs require --confirm-actions",
                param_hint="--confirm-actions",
            )
        if not confirm_actions and not typer.confirm(
            "Resume an action-capable experiment? Every Tyr action still requires approval",
            default=False,
        ):
            raise typer.Abort()

    task_directory = resolve_task_directory(settings.task_root, source_record.task)
    task = load_task(task_directory)

    selected_model = model or configuration.model or settings.model_name
    selected_scientist_model = scientist_model or settings.scientist_model_name or selected_model
    selected_judge_model = (
        judge_model or getattr(settings, "judge_model_name", "") or selected_model
    )
    trace_port = getattr(settings, "trace_port", None) or getattr(
        main_cli, "create_trace_port", create_trace_port
    )(settings)
    try:
        (
            artifact_store,
            target,
            collector,
            sandbox,
            model_gateway,
            scientist_model_gateway,
            judge_model_gateway,
        ) = build_experiment_execution(
            settings,
            selected_model,
            selected_scientist_model,
            selected_judge_model,
            trace_port=trace_port,
        )
    except TypeError:
        (
            artifact_store,
            target,
            collector,
            sandbox,
            model_gateway,
            scientist_model_gateway,
            judge_model_gateway,
        ) = build_experiment_execution(
            settings, selected_model, selected_scientist_model, selected_judge_model
        )

    configuration = configuration.model_copy(
        update={
            "model": selected_model,
            "scientist_model": selected_scientist_model,
            "judge_model": selected_judge_model,
        }
    )

    new_run_id = new_id()
    started_at = datetime.now(UTC)
    run_document = RunRecord(
        id=new_run_id,
        source=RunSource.CLI,
        task=source_record.task,
        state=RunState.RUNNING,
        configuration=configuration,
        retryOf=run_id,
        createdAt=started_at,
        updatedAt=started_at,
    )

    async def run_live() -> ExecutionOutput:
        try:
            return await ExperimentExecutionService().resume_scientist(
                task,
                configuration,
                source_run_id=run_id,
                run_id=new_run_id,
                target=target,
                model=model_gateway,
                scientist_model=scientist_model_gateway,
                judge_model=judge_model_gateway,
                artifacts=artifact_store,
                activity_sink=FilesystemActivitySink(artifact_store),
                progress=render_progress_cb,
                delivery_verifier=collector,
                content_evidence_provider=collector,
                sandbox=sandbox,
                scientist_output_tokens=settings.scientist_output_tokens,
                trace_port=trace_port,
            )
        finally:
            await target.aclose()
            if collector is not None:
                await collector.aclose()

    execute_cli_run(console, run_document, artifact_store, run_live, trace_port=trace_port)
