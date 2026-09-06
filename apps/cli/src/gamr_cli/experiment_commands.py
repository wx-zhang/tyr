from __future__ import annotations

from pathlib import Path

import typer

from .experiment_cli import resume_research_command, run_experiment_command
from .llm_logging import LlmLogMode

experiment_app = typer.Typer(help="Create and inspect Experiment Presets and Experiments")


@experiment_app.command("run")
def run_experiment(
    directory: Path,
    action_mode: str = typer.Option("read_only", "--action-mode"),
    model: str = typer.Option("", "--model", help="Override GAMR_MODEL_NAME."),
    adversarial_researcher_model: str = typer.Option(
        "",
        "--adversarial-researcher-model",
        "--scientist-model",
        help="Override GAMR_ADVERSARIAL_RESEARCHER_MODEL_NAME.",
    ),
    judge_model: str = typer.Option("", "--judge-model", help="Override GAMR_JUDGE_MODEL_NAME."),
    approval_gated: bool = typer.Option(
        False,
        "--approval-gated",
        "--allow-actions",
        help=(
            "Enable Approval-gated mode. GAMR requests actions; Tyr requires a "
            "human decision for every action."
        ),
    ),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm an Approval-gated experiment without an interactive prompt.",
    ),
    scenario_id: list[str] = typer.Option(
        [],
        "--scenario-id",
        "--case-id",
        help="Select a Scenario; repeat to run multiple Scenarios in manifest order.",
    ),
    all_scenarios: bool = typer.Option(
        False, "--all-scenarios", "--all-cases", help="Run every Scenario in the Task."
    ),
    max_concurrent_scenario_executions: int = typer.Option(
        5,
        "--max-concurrent-scenario-executions",
        "--max-concurrent-cases",
        min=1,
        max=5,
        help="Maximum concurrent Scenario Executions.",
    ),
    research_iterations: int = typer.Option(
        0,
        "--research-iterations",
        "--scientist-iterations",
        min=0,
        help="Generate and run bounded Research Iterations.",
    ),
    history_test_runs: int = typer.Option(
        10, "--history-test-runs", min=0, max=100, help="Use latest base Scenarios as history."
    ),
    history_research_runs: int = typer.Option(
        5,
        "--history-research-runs",
        "--history-scientist-runs",
        min=0,
        max=100,
        help="Use latest Research Iterations as history.",
    ),
    discovery_input: Path | None = typer.Option(
        None,
        "--discovery-input",
        help="Load a validated operator-provided discovery target from a local JSON file.",
    ),
    fallback_to_discovery: bool = typer.Option(
        False,
        "--fallback-to-discovery",
        help="Run a bounded read-only preflight and fall back to live discovery if unavailable.",
    ),
    log_llm: LlmLogMode = typer.Option(
        LlmLogMode.DEFAULT,
        "--log-llm",
        help="Log provider thinking as it streams.",
    ),
) -> None:
    """Run a Task through the shared engine and write an Experiment bundle."""
    from . import main as main_cli

    run_experiment_command(
        console=main_cli.console,
        directory=directory,
        action_mode=action_mode,
        model=model,
        adversarial_researcher_model=adversarial_researcher_model,
        discovery_input=discovery_input,
        fallback_to_discovery=fallback_to_discovery,
        judge_model=judge_model,
        allow_actions=approval_gated,
        confirm_actions=confirm_actions,
        scenario_id=scenario_id,
        all_scenarios=all_scenarios,
        max_concurrent_scenario_executions=max_concurrent_scenario_executions,
        research_iterations=research_iterations,
        history_test_runs=history_test_runs,
        history_research_runs=history_research_runs,
        log_llm=log_llm,
        render_progress_cb=main_cli._render_progress,
    )


@experiment_app.command("resume-research")
def resume_research_experiment(
    run_id: str,
    research_iterations: int = typer.Option(
        0,
        "--research-iterations",
        "--scientist-iterations",
        min=0,
        help="Override the source Experiment's researchIterations.",
    ),
    model: str = typer.Option("", "--model", help="Override GAMR_MODEL_NAME."),
    adversarial_researcher_model: str = typer.Option(
        "",
        "--adversarial-researcher-model",
        "--scientist-model",
        help="Override GAMR_ADVERSARIAL_RESEARCHER_MODEL_NAME.",
    ),
    judge_model: str = typer.Option("", "--judge-model", help="Override GAMR_JUDGE_MODEL_NAME."),
    confirm_actions: bool = typer.Option(
        False,
        "--confirm-actions",
        help="Confirm an Approval-gated resume without an interactive prompt.",
    ),
    log_llm: LlmLogMode = typer.Option(
        LlmLogMode.DEFAULT,
        "--log-llm",
        help="Log provider thinking as it streams.",
    ),
) -> None:
    """Resume the Adversarial Researcher with prior Scenario history."""
    from . import main as main_cli

    resume_research_command(
        console=main_cli.console,
        run_id=run_id,
        research_iterations=research_iterations,
        model=model,
        adversarial_researcher_model=adversarial_researcher_model,
        judge_model=judge_model,
        confirm_actions=confirm_actions,
        log_llm=log_llm,
        render_progress_cb=main_cli._render_progress,
    )


@experiment_app.command("resume-scientist")
def resume_scientist_compatibility(
    run_id: str,
    scientist_iterations: int = typer.Option(
        0, "--scientist-iterations", min=0, help="Legacy alias for --research-iterations."
    ),
    model: str = typer.Option("", "--model"),
    scientist_model: str = typer.Option("", "--scientist-model"),
    judge_model: str = typer.Option("", "--judge-model"),
    confirm_actions: bool = typer.Option(False, "--confirm-actions"),
    log_llm: LlmLogMode = typer.Option(
        LlmLogMode.DEFAULT,
        "--log-llm",
        help="Log provider thinking as it streams.",
    ),
) -> None:
    from . import main as main_cli

    resume_research_command(
        console=main_cli.console,
        run_id=run_id,
        research_iterations=scientist_iterations,
        model=model,
        adversarial_researcher_model=scientist_model,
        judge_model=judge_model,
        confirm_actions=confirm_actions,
        log_llm=log_llm,
        render_progress_cb=main_cli._render_progress,
    )
