from __future__ import annotations

from gamr_core import RunActivity
from gamr_engine.runner import ProgressEvent
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding


def render_progress(console: Console, event: ProgressEvent) -> None:
    context = _context(event)
    if event.event_type == "run.started":
        console.print(
            f"[bold cyan]GAMR[/] [dim]· Tyr's final opponent ·[/] "
            f"{escape(event.detail or 'starting')} "
            f"[dim](run {escape(event.run_id)})[/]"
        )
    elif event.event_type == "tyr.connecting":
        console.print("[cyan]◌[/] Connecting to Tyr…")
    elif event.event_type == "tyr.connected":
        console.print("[green]✓[/] Tyr connection ready")
    elif event.event_type == "tyr.failed":
        console.print(f"[red]✗[/] Tyr connection failed [dim]({escape(event.detail or '')})[/]")
    elif event.event_type == "discovery.started":
        console.print("[bold blue]▸[/] Discovery")
    elif event.event_type == "discovery.completed":
        console.print(f"[green]✓[/] Discovery complete [dim]· {escape(event.detail or '')}[/]")
    elif event.event_type == "scientist.started":
        console.print(
            f"[bold blue]▸[/] Scientist [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "scientist.scenario_ready":
        console.print(
            f"[green]✓[/] Scientist scenario ready "
            f"[cyan]{escape(event.case_id or '')}[/]"
            f"[dim] · {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "scientist.failed":
        console.print(
            f"[red]✗[/] Scientist failed [dim]({escape(event.detail or '')})[/]"
        )
    elif event.event_type == "scientist.completed":
        console.print(
            f"[green]✓[/] Scientist complete [dim]· {escape(event.detail or '')}[/]"
        )
    elif event.event_type == "case.started":
        console.print(f"[bold blue]▸[/] Case [cyan]{escape(event.case_id or '')}[/]")
    elif event.event_type == "model.thinking":
        console.print(f"[yellow]✦[/] [dim]{context}[/] Thinking…")
    elif event.event_type == "target.requesting":
        console.print(f"[magenta]↗[/] [dim]{context}[/] Sending to Tyr…")
        _print_message(console, event.detail, style="magenta")
    elif event.event_type == "target.completed":
        console.print(f"[green]↘[/] [dim]{context}[/] Tyr replied")
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
        console.print(f"[green]✓[/] [dim]{context}[/] Turn complete")
    elif event.event_type == "assessment.started":
        console.print(f"[yellow]◌[/] [dim]{context}[/] Assessing evidence…")
    elif event.event_type == "assessment.completed":
        console.print(f"[green]✓[/] [dim]{context}[/] Assessment ready")
    elif event.event_type == "case.completed":
        console.print(
            f"[green]✓[/] Case [cyan]{escape(event.case_id or '')}[/] "
            f"[dim]· {escape(event.detail or '')}[/]"
        )


class ConsoleActivitySink:
    def __init__(self, console: Console) -> None:
        self.console = console
        self._latest: dict[str, int] = {}

    def latest_sequence(self, run_id: str) -> int:
        return self._latest.get(run_id, 0)

    def append(self, activity: RunActivity) -> RunActivity:
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
                case_id=activity.case_id,
                turn=metadata_turn if isinstance(metadata_turn, int) else None,
                detail=activity.summary,
            ),
        )
        return activity


def _context(event: ProgressEvent) -> str:
    parts = [escape(event.case_id)] if event.case_id else []
    if not parts and event.phase:
        parts.append(escape(event.phase.title()))
    if event.turn is not None:
        parts.append(f"turn {event.turn}")
    return " · ".join(parts) or "Run"


def _print_message(console: Console, detail: str | None, *, style: str) -> None:
    if not detail or not detail.strip():
        return
    console.print(Padding(Markdown(detail.strip(), style=style), (0, 0, 0, 2)))
