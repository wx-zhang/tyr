from io import StringIO
from unittest.mock import patch

from gamr_cli.progress import render_progress
from gamr_engine.experiments.records import ProgressEvent
from rich.console import Console
from rich.progress import Progress


def test_wait_timer_retains_elapsed_time_when_response_arrives() -> None:
    output = StringIO()
    console = Console(file=output, width=120)
    clock = [10.0]
    with patch(
        "gamr_cli.progress.Progress",
        side_effect=lambda *args, **kwargs: Progress(*args, **kwargs, get_time=lambda: clock[0]),
    ):
        render_progress(console, ProgressEvent("target.requesting", "run", turn=1))
        clock[0] = 75.0
        render_progress(console, ProgressEvent("target.completed", "run", turn=1, detail="reply"))
    rendered = output.getvalue()
    assert "Waiting for Tyr" in rendered
    assert "Tyr replied" in rendered
    assert "0:01:05" in rendered
