from __future__ import annotations

from gamr_core import ExperimentActivity
from gamr_engine.experiments.records import ProgressEvent
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding
from rich.progress import Progress, TaskID, TextColumn, TimeElapsedColumn
from rich.text import Text

_waits: dict[Console, tuple[Progress, dict[tuple[str, str | None, int | None], TaskID]]] = {}


def _update_wait(console: Console, event: ProgressEvent) -> None:
    key = (event.run_id, event.scenario_execution_id or event.case_id or event.phase, event.turn)
    if event.event_type == "target.requesting":
        if console not in _waits:
            progress = Progress(
                TextColumn("{task.description}", markup=False),
                TimeElapsedColumn(),
                console=console,
                refresh_per_second=4,
            )
            _waits[console] = (progress, {})
            progress.start()
        progress, tasks = _waits[console]
        tasks[key] = progress.add_task(f"  Waiting for Tyr… · {_context(event)} ·", total=None)
    elif console in _waits:
        progress, tasks = _waits[console]
        for pending in list(tasks):
            if pending == key and event.event_type in {"target.completed", "target.failed"}:
                progress.stop_task(tasks.pop(pending))
            elif pending[0] == event.run_id and event.event_type in {
                "run.completed",
                "run.failed",
                "run.interrupted",
                "run.cancelled",
            }:
                progress.stop_task(tasks.pop(pending))
        if not tasks:
            progress.stop()
            del _waits[console]


def render_progress(console: Console, event: ProgressEvent) -> None:
    if event.event_type != "target.requesting":
        _update_wait(console, event)
    context = _context(event)
    scenario_id = escape(event.scenario_id or event.case_id or "")
    scenario_execution_id = escape(event.scenario_execution_id or event.case_id or "")
    if event.event_type == "run.started":
        console.print(
            f"[bold cyan]GAMR[/] [dim]· Tyr's final opponent ·[/] "
            f"{escape(event.detail or 'starting')} "
            f"[dim](Experiment {escape(event.run_id)})[/]"
        )
    elif event.event_type == "tyr.connecting":
        console.print("[cyan]◌[/] Connecting to Tyr…")
    elif event.event_type == "tyr.connected":
        console.print("[green]✓[/] Tyr connection ready")
    elif event.event_type == "tyr.failed":
        console.print(f"[red]✗[/] Tyr connection failed [dim]({escape(event.detail or '')})[/]")
    elif event.event_type == "discovery.preflight.started":
        console.print("[bold blue]▸[/] Provided-target preflight [dim]· read-only[/]")
    elif event.event_type == "discovery.preflight.completed":
        console.print(
            f"[green]✓[/] Provided-target preflight [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "discovery.preflight.failed":
        console.print(
            f"[yellow]↳[/] Falling back to live discovery [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "discovery.started":
        console.print("[bold blue]▸[/] Discovery")
    elif event.event_type == "discovery.completed":
        console.print(f"[green]✓[/] Discovery complete [dim]· {escape(event.detail or '')}[/]")
        if event.fields:
            width = max(len(name) for name, _ in event.fields)
            for name, value in event.fields:
                label = f"{name:<{width}}"
                console.print(f"  [cyan]{escape(label)}[/]  {escape(value)}")
    elif event.event_type == "scientist.started":
        console.print(
            f"[bold blue]▸[/] Adversarial Researcher [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "scientist.history_used":
        console.print(f"[cyan]↳[/] Research history [dim]· {escape(event.detail or '')}[/]")
        if event.history_case_ids:
            for history_scenario_id in event.history_case_ids:
                console.print(f"  [cyan]•[/] Scenario {escape(history_scenario_id)}")
    elif event.event_type == "scientist.scenario_ready":
        console.print(
            "[green]✓[/] Adversarial Researcher Scenario ready "
            f"[cyan]{scenario_id}[/]"
            f"[dim] · {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "scientist.failed":
        console.print(
            f"[red]✗[/] Adversarial Researcher failed [dim]({escape(event.detail or '')})[/]"
        )
    elif event.event_type == "scientist.skipped":
        console.print(
            f"[yellow]⊘[/] Adversarial Researcher skipped [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "scientist.completed":
        console.print(f"[green]✓[/] Research complete [dim]· {escape(event.detail or '')}[/]")
    elif event.event_type == "case.started":
        console.print(f"[bold blue]▸[/] Scenario Execution [cyan]{scenario_execution_id}[/]")
    elif event.event_type == "model.thinking":
        console.print(f"[yellow]✦[/] [dim]{context}[/] Thinking…")
    elif event.event_type == "target.requesting":
        console.print(f"[magenta]↗[/] [dim]{context}[/] Sending to Tyr…")
        _print_message(console, event.detail, style="magenta")
        _update_wait(console, event)
    elif event.event_type == "target.completed":
        settlement_state = dict(event.fields or ()).get("settlementState")
        label = (
            "Tyr is waiting for peer-owner approval"
            if settlement_state == "peer_approval_blocked"
            else "Tyr is waiting for approval"
            if settlement_state == "waiting_for_approval"
            else "Tyr replied"
        )
        console.print(f"[green]↘[/] [dim]{context}[/] {label}")
        if event.fields and ("replySource", "delegated bridge follow-up") in event.fields:
            console.print("  [dim]↳ Settled delegated bridge follow-up[/]")
        _print_message(console, event.detail, style="green")
    elif event.event_type == "target.failed":
        console.print(
            f"[red]✗[/] [dim]{context}[/] Tyr call failed [dim]({escape(event.detail or '')})[/]"
        )
    elif event.event_type == "model.failed":
        console.print(
            f"[red]✗[/] [dim]{context}[/] Model request failed "
            f"[dim]({escape(event.detail or '')})[/]"
        )
    elif event.event_type == "turn.completed":
        settlement_state = dict(event.fields or ()).get("settlementState")
        if settlement_state in {"peer_approval_blocked", "waiting_for_approval", "timeout"}:
            detail = (
                "target timed out" if settlement_state == "timeout" else "target awaiting approval"
            )
            console.print(f"[yellow]◌[/] [dim]{context}[/] Turn recorded · {detail}")
        else:
            console.print(f"[green]✓[/] [dim]{context}[/] Turn complete")
    elif event.event_type == "assessment.started":
        console.print(f"[yellow]◌[/] [dim]{context}[/] Assessing evidence…")
    elif event.event_type == "assessment.completed":
        console.print(
            f"[green]✓[/] [dim]{context}[/] Assessment ready"
            + (f" [dim]· {escape(event.detail)}[/]" if event.detail else "")
        )
        if event.fields:
            for name, value in event.fields:
                if name == "summary":
                    _print_message(console, value, style="yellow")
                else:
                    console.print(f"  [cyan]{escape(name)}[/]  {escape(value)}")
    elif event.event_type == "case.completed":
        console.print(
            "[green]✓[/] Scenario Execution "
            f"[cyan]{scenario_execution_id}[/] "
            f"[dim]· {escape(event.detail or '')}[/]"
        )


class ConsoleActivitySink:
    def __init__(self, console: Console) -> None:
        self.console = console
        self._latest: dict[str, int] = {}

    def latest_sequence(self, run_id: str) -> int:
        return self._latest.get(run_id, 0)

    def append(self, activity: ExperimentActivity) -> ExperimentActivity:
        self._latest[activity.run_id] = activity.sequence
        metadata_event = activity.metadata.get("eventType")
        event_type = (
            metadata_event if isinstance(metadata_event, str) else activity.activity_type.value
        )
        metadata_turn = activity.metadata.get("turn")
        render_progress(
            self.console,
            ProgressEvent(
                event_type,
                activity.run_id,
                phase=activity.phase,
                case_id=activity.scenario_id,
                scenario_id=activity.scenario_id,
                scenario_execution_id=activity.scenario_execution_id,
                turn=metadata_turn if isinstance(metadata_turn, int) else None,
                detail=activity.summary,
                fields=tuple(
                    (key, value)
                    for key in ("replySource", "settlementState")
                    if isinstance(value := activity.metadata.get(key), str)
                )
                or None,
                history_case_ids=tuple(activity.related_case_ids),
            ),
        )
        return activity


def _context(event: ProgressEvent) -> str:
    parts = []
    if event.scenario_execution_id:
        parts.append(f"Scenario Execution {escape(event.scenario_execution_id)}")
    elif event.scenario_id:
        parts.append(f"Scenario {escape(event.scenario_id)}")
    elif event.phase:
        parts.append(escape(event.phase.title()))
    if event.turn is not None:
        parts.append(f"turn {event.turn}")
    return " · ".join(parts) or "Experiment"


def _print_message(console: Console, detail: str | None, *, style: str) -> None:
    if not detail or not detail.strip():
        return
    message = Markdown(detail.strip(), style=style)
    has_html = any(
        token.type in {"html_inline", "html_block"}
        for block in message.parsed
        for token in (block, *(block.children or []))
    )
    rendered = Text(detail.strip(), style=style) if has_html else message
    console.print(Padding(rendered, (0, 0, 0, 2)))
