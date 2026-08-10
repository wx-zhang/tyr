from __future__ import annotations

from gamr_core import RunResult


def render_markdown(result: RunResult) -> str:
    lines = [
        f"# Run {result.run_id}",
        "",
        f"Outcome: `{result.outcome}`",
        "",
        (
            "Summary: "
            f"{result.summary.vulnerable} vulnerable, "
            f"{result.summary.protected} protected, "
            f"{result.summary.inconclusive} inconclusive"
        ),
        "",
        "| Case | Outcome | Objective | Verdict | Summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {case.scenario_id} | {case.outcome} | {case.objective_status} | "
        f"{case.verdict} | {case.summary.replace('|', '\\|')} |"
        for case in result.cases
    )
    if result.errors:
        lines.extend(["", "## Errors", "", *[f"- {error}" for error in result.errors]])
    return "\n".join(lines) + "\n"
