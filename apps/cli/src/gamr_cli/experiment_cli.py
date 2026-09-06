from __future__ import annotations

import json
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
    DiscoveryInputDocument,
    ExperimentPresetConfig,
    ExperimentRecord,
    ExperimentSource,
    ExperimentState,
)
from gamr_core.identifiers import new_id
from gamr_engine import ExecutionOutput, ExperimentExecutionService
from rich.console import Console

from .composition import configured_secrets
from .llm_logging import LlmLogMode, model_stream_callback
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
    adversarial_researcher_model: str,
    judge_model: str,
    allow_actions: bool,
    confirm_actions: bool,
    scenario_id: list[str],
    all_scenarios: bool,
    max_concurrent_scenario_executions: int,
    research_iterations: int,
    history_test_runs: int,
    history_research_runs: int,
    discovery_input: Path | None,
    fallback_to_discovery: bool,
    log_llm: LlmLogMode,
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
    provided_document: DiscoveryInputDocument | None = None
    if discovery_input is not None:
        try:
            provided_document = DiscoveryInputDocument.model_validate(
                json.loads(discovery_input.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError) as error:
            raise typer.BadParameter(
                f"invalid discovery input: {error}",
                param_hint="--discovery-input",
            ) from error
    if fallback_to_discovery and provided_document is None:
        raise typer.BadParameter(
            "--fallback-to-discovery requires --discovery-input",
            param_hint="--fallback-to-discovery",
        )
    task = load_fn(directory)
    if scenario_id and all_scenarios:
        raise typer.BadParameter("use --scenario-id or --all-scenarios, not both")
    selected_scenario_ids = (
        [scenario.metadata.id for scenario in task.scenarios]
        if all_scenarios
        else scenario_id or None
    )
    settings_cls = getattr(main_cli, "Settings", Settings)
    settings = settings_cls()
    selected_model = model or settings.model_name
    selected_adversarial_researcher_model = (
        adversarial_researcher_model or settings.adversarial_researcher_model_name or selected_model
    )
    selected_judge_model = (
        judge_model or getattr(settings, "judge_model_name", "") or selected_model
    )
    trace_port = getattr(settings, "trace_port", None) or getattr(
        main_cli, "create_trace_port", create_trace_port
    )(settings)
    stream_callback = model_stream_callback(console, log_llm)
    build_fn = getattr(main_cli, "build_experiment_execution", build_experiment_execution)
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
        selected_adversarial_researcher_model,
        selected_judge_model,
        trace_port=trace_port,
        stream_callback=stream_callback,
    )

    configuration = ExperimentPresetConfig(
        actionMode=action_mode,
        model=selected_model,
        adversarialResearcherModel=selected_adversarial_researcher_model,
        judgeModel=selected_judge_model,
        maxTurns=task.manifest.spec.defaults.max_turns,
        discoveryTurns=20,
        scenarioIds=selected_scenario_ids,
        discoveryInput=provided_document,
        fallbackToDiscovery=fallback_to_discovery,
        maxConcurrentScenarioExecutions=max_concurrent_scenario_executions,
        researchIterations=research_iterations,
        historyTestRuns=history_test_runs,
        historyResearchRuns=history_research_runs,
    )
    run_id = new_id()
    started_at = datetime.now(UTC)
    run_document = ExperimentRecord(
        id=run_id,
        source=ExperimentSource.CLI,
        task=str(directory),
        state=ExperimentState.RUNNING,
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
                scientist_output_tokens=settings.adversarial_researcher_output_tokens,
                trace_port=trace_port,
            )
        finally:
            await target.aclose()
            if collector is not None:
                await collector.aclose()

    execute_cli_run(console, run_document, artifact_store, run_live, trace_port=trace_port)


def resume_research_command(
    console: Console,
    run_id: str,
    research_iterations: int,
    model: str,
    adversarial_researcher_model: str,
    judge_model: str,
    confirm_actions: bool,
    log_llm: LlmLogMode,
    render_progress_cb: Any,
) -> None:
    from . import main as main_cli

    settings = getattr(main_cli, "Settings", Settings)()
    artifact_store = FilesystemArtifactStore(
        settings.artifact_root,
        secrets=configured_secrets(settings),
    )
    try:
        source_record = ExperimentRecord.model_validate(
            artifact_store.read_json(run_id, "run.json")
        )
    except FileNotFoundError:
        raise typer.BadParameter(f"run does not exist: {run_id}", param_hint="run_id") from None

    configuration = source_record.configuration
    if research_iterations:
        configuration = configuration.model_copy(
            update={"research_iterations": research_iterations}
        )
    if not configuration.research_iterations:
        raise typer.BadParameter(
            "source experiment has researchIterations=0; pass --research-iterations",
            param_hint="--research-iterations",
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
    selected_adversarial_researcher_model = (
        adversarial_researcher_model or settings.adversarial_researcher_model_name or selected_model
    )
    selected_judge_model = (
        judge_model or getattr(settings, "judge_model_name", "") or selected_model
    )
    trace_port = getattr(settings, "trace_port", None) or getattr(
        main_cli, "create_trace_port", create_trace_port
    )(settings)
    stream_callback = model_stream_callback(console, log_llm)
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
        selected_adversarial_researcher_model,
        selected_judge_model,
        trace_port=trace_port,
        stream_callback=stream_callback,
    )

    configuration = configuration.model_copy(
        update={
            "model": selected_model,
            "adversarial_researcher_model": selected_adversarial_researcher_model,
            "judge_model": selected_judge_model,
        }
    )

    new_run_id = new_id()
    started_at = datetime.now(UTC)
    run_document = ExperimentRecord(
        id=new_run_id,
        source=ExperimentSource.CLI,
        task=source_record.task,
        state=ExperimentState.RUNNING,
        configuration=configuration,
        retryOf=run_id,
        createdAt=started_at,
        updatedAt=started_at,
    )

    async def run_live() -> ExecutionOutput:
        try:
            return await ExperimentExecutionService().resume_research(
                task,
                configuration,
                source_run_id=run_id,
                run_id=new_run_id,
                target=target,
                model=model_gateway,
                scientist_model=scientist_model_gateway,
                artifacts=artifact_store,
                activity_sink=FilesystemActivitySink(artifact_store),
                progress=render_progress_cb,
                delivery_verifier=collector,
                content_evidence_provider=collector,
                sandbox=sandbox,
                scientist_output_tokens=settings.adversarial_researcher_output_tokens,
                trace_port=trace_port,
            )
        finally:
            await target.aclose()
            if collector is not None:
                await collector.aclose()

    execute_cli_run(console, run_document, artifact_store, run_live, trace_port=trace_port)
