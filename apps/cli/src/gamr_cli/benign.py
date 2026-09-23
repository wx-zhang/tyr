from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from gamr_adapters.benign_config import BenignSettings
from gamr_adapters.benign_model import BenignModel
from gamr_adapters.benign_store import BenignStore
from gamr_adapters.benign_worker import BenignWorker
from gamr_core.benign import BenignScenario, Submission

app = typer.Typer(help="Benign functional scenario tests. No GAMR attack loop.")


@app.command()
def draft(text: str, workspace: str = typer.Option(...), timezone: str = typer.Option(...)) -> None:
    """Compile and save a scenario. Does not contact Tyr."""
    store = BenignStore(BenignSettings().root)
    scenario = asyncio.run(BenignModel(store).draft(text, workspace, timezone))
    typer.echo(scenario.model_dump_json(indent=2))
    typer.echo(f"Saved: {store.directory(scenario.id) / 'scenario.json'}", err=True)


@app.command()
def validate(path: Path) -> None:
    """Validate a scenario document without contacting a provider."""
    scenario = BenignScenario.model_validate_json(path.read_text())
    typer.echo(f"Valid: {scenario.title}")


@app.command()
def run(
    paths: list[Path],
    repeat: int = 1,
    concurrency: int = 1,
    approval_gated: bool = False,
    confirm_actions: bool = False,
) -> None:
    """Queue one or more scenarios. A separate worker executes them."""
    settings = BenignSettings()
    submission = Submission(
        scenarios=[BenignScenario.model_validate_json(path.read_text()) for path in paths],
        repeat=repeat,
        concurrency=concurrency,
        action_mode="approval_required" if approval_gated else "read_only",
        confirmed=confirm_actions,
    )
    settings.validate_submission(submission)
    runs = BenignStore(settings.root).enqueue(submission)
    typer.echo(json.dumps({"batch_id": runs[0].batch_id, "run_ids": [r.id for r in runs]}))


@app.command()
def show(run_id: str) -> None:
    """Read a retained result and its observations without running anything."""
    typer.echo(BenignStore(BenignSettings().root).read(run_id).model_dump_json(indent=2))


@app.command()
def resume(run_id: str) -> None:
    """Poll an existing pending operation after input or approval in Tyr."""
    BenignWorker(BenignSettings()).resume(run_id)
    typer.echo("Resume queued. No approval decision sent.")


@app.command()
def worker() -> None:
    """Run the durable benign queue, independently of API reloads."""
    asyncio.run(BenignWorker(BenignSettings()).serve())


if __name__ == "__main__":
    app()
