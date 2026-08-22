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
    decoding_cases = [
        case for case in result.cases
        if case.content_overlap and case.content_overlap.decoding
    ]
    if decoding_cases:
        lines.extend(["", "## Trajectory Decoding", ""])
        for case in decoding_cases:
            assert case.content_overlap is not None
            dec = case.content_overlap.decoding
            assert dec is not None
            details = [f"status `{dec.status.value}`", f"attempts {dec.attempt_count}"]
            if dec.failure_code:
                details.append(f"failure `{dec.failure_code.value}`")
            if dec.derived_files:
                details.append(f"derived files {len(dec.derived_files)}")
            lines.append(f"- **{case.scenario_id}**: {', '.join(details)}")
    if result.errors:
        lines.extend(["", "## Errors", "", *[f"- {error}" for error in result.errors]])
    return "\n".join(lines) + "\n"
