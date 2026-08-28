from __future__ import annotations

from gamr_core import ExperimentResult


def _safe_report_text(value: str, limit: int) -> str:
    return value[:limit]


def render_markdown(result: ExperimentResult) -> str:
    lines = [
        f"# Experiment {result.run_id}",
        "",
        f"Completion Outcome: `{result.outcome}`",
        "",
        (
            "Summary: "
            f"{result.summary.vulnerable} vulnerable, "
            f"{result.summary.protected} protected, "
            f"{result.summary.inconclusive} inconclusive"
        ),
        "",
        (
            "| Scenario | Scenario Execution | Completion Outcome | "
            "Objective Status | Security Verdict | Summary |"
        ),
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        (
            f"| {scenario.scenario_id} | {scenario.scenario_execution_id} | "
            f"{scenario.outcome} | {scenario.objective_status} | "
            f"{scenario.verdict} | {scenario.summary.replace('|', '\\|')} |"
        )
        for scenario in result.scenario_executions
    )
    decoding_scenarios = [
        scenario
        for scenario in result.scenario_executions
        if scenario.content_overlap and scenario.content_overlap.decoding
    ]
    if decoding_scenarios:
        lines.extend(["", "## Trajectory Decoding", ""])
        for scenario in decoding_scenarios:
            assert scenario.content_overlap is not None
            dec = scenario.content_overlap.decoding
            assert dec is not None
            details = [f"status `{dec.status.value}`", f"attempts {dec.attempt_count}"]
            if dec.action:
                details.append(f"route `{dec.action}`")
            if dec.failure_code:
                details.append(f"failure `{dec.failure_code.value}`")
            if dec.derived_files:
                details.append(f"derived files {len(dec.derived_files)}")
            lines.append(
                f"- **{scenario.scenario_id}** / `{scenario.scenario_execution_id}`: "
                f"{', '.join(details)}"
            )
            if dec.rationale:
                lines.append(f"  - Rationale: {_safe_report_text(dec.rationale, 600)}")
            for attempt in dec.attempts:
                lines.append(
                    f"  - Attempt {attempt.attempt}: stage `{attempt.stage}`, "
                    f"program `{attempt.program_sha256}`"
                )
                if attempt.source:
                    lines.extend(
                        [
                            "    - Executed source:",
                            "",
                            "      ```python",
                            _safe_report_text(attempt.source, 65_536),
                            "      ```",
                        ]
                    )
                if attempt.execution:
                    execution = attempt.execution
                    lines.append(
                        f"    - Result: exit `{execution.exit_code}`, "
                        f"elapsed `{execution.elapsed_seconds:.3f}s`, "
                        f"stdout `{execution.stdout.state}`, stderr `{execution.stderr.state}`"
                    )
                    for name, stream in (
                        ("stdout", execution.stdout),
                        ("stderr", execution.stderr),
                    ):
                        if stream.state == "captured" and stream.value:
                            lines.append(
                                f"      - {name}: "
                                f"`{_safe_report_text(stream.value, 16_384)}`"
                            )
                if attempt.failure_code:
                    lines.append(f"    - Failure: `{attempt.failure_code.value}`")
    if result.errors:
        lines.extend(["", "## Errors", "", *[f"- {error}" for error in result.errors]])
    return "\n".join(lines) + "\n"
