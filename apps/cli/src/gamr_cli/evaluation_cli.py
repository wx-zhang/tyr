from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import typer
from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_core.identifiers import new_id
from rich.console import Console
from rich.table import Table

from .composition import build_sandbox, configured_secrets
from .judge_evaluation import load_evaluation_dataset, run_evaluation_dataset
from .judge_evaluation_debug import RichDebugOutput, new_debug_log_path


def run_judge_evaluation_command(
    console: Console,
    dataset_path: Path,
    model_name: str,
    case_ids: list[str],
    debug: bool,
) -> None:
    console.print(f"Loading judge dataset: [cyan]{dataset_path}[/cyan]")
    settings = Settings()
    if not settings.model_api_key:
        raise typer.BadParameter("OPENROUTER_API_KEY is required")
    selected_model = model_name or settings.judge_model_name or settings.model_name
    if not selected_model:
        raise typer.BadParameter("--model, TYR_LOOP_JUDGE_MODEL, or TYR_LOOP_MODEL is required")
    if settings.sandbox_backend != "docker":
        raise typer.BadParameter("judge evaluation requires GAMR_SANDBOX_BACKEND=docker")

    dataset = load_evaluation_dataset(dataset_path)
    if case_ids:
        selected = [case for case in dataset.cases if case.id in set(case_ids)]
        missing = sorted(set(case_ids) - {case.id for case in selected})
        if missing:
            raise typer.BadParameter(f"unknown evaluation case IDs: {', '.join(missing)}")
        dataset = replace(dataset, cases=selected)

    evaluation_id = new_id()
    artifact_root = Path(settings.artifact_root)
    output_root = artifact_root / "evaluations" / "judges" / evaluation_id
    console.print(
        f"Evaluation [cyan]{evaluation_id}[/cyan] · {len(dataset.cases)} cases · "
        f"model [cyan]{selected_model}[/cyan]"
    )
    console.print(f"Tyr disabled · results: [cyan]{output_root}[/cyan]")
    secrets = configured_secrets(settings)
    debug_output = None
    if debug:
        debug_log_path = new_debug_log_path(artifact_root)
        debug_output = RichDebugOutput(console, debug_log_path, secrets=secrets)
        console.print(
            "WARNING: --debug prints unredacted LLM and sandbox diagnostics.",
            style="bold yellow",
        )
        console.print(f"Redacted debug log: [cyan]{debug_log_path}[/cyan]")
    model = OpenAICompatibleModel(
        settings.model_base_url,
        settings.model_api_key,
        selected_model,
    )
    summary = asyncio.run(
        run_evaluation_dataset(
            dataset,
            model=model,
            sandbox=build_sandbox(settings),
            output_root=output_root,
            evaluation_id=evaluation_id,
            secrets=secrets,
            progress=lambda message: console.print(message, style="dim", markup=False),
            debug=debug_output,
        )
    )

    table = Table("Case", "Label", "Result")
    for case in summary["cases"]:
        passed = bool(case["passed"])
        table.add_row(
            str(case["id"]),
            str(case["label"]),
            "[green]PASS[/green]" if passed else "[red]FAIL[/red]",
        )
    console.print(table)
    console.print(output_root / "summary.json")
    if not summary["passed"]:
        raise typer.Exit(code=1)
