from io import StringIO

from gamr_cli.progress import render_progress
from gamr_engine.experiments.records import ProgressEvent
from rich.console import Console


def test_progress_preserves_angle_bracketed_target_evidence() -> None:
    output = StringIO()
    render_progress(
        Console(file=output, width=120),
        ProgressEvent(
            "target.completed",
            "run",
            phase="case",
            turn=4,
            detail="APPROVAL: <approval state unknown>",
        ),
    )
    assert "APPROVAL: <approval state unknown>" in output.getvalue()
