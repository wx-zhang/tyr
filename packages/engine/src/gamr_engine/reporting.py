from __future__ import annotations

import re

from gamr_core import RunResult

_BEARER = re.compile(r"Bearer\s+[^\s,;]+", re.I)
_HOST_PATH = re.compile(
    r"/(?:tmp|private/tmp|Users|home|var/run/docker|var/folders)[^\s'\"]*", re.I
)


def _safe_report_text(value: str, limit: int) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _HOST_PATH.sub("[REDACTED_PATH]", value)
    return value[:limit]


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
        case for case in result.cases if case.content_overlap and case.content_overlap.decoding
    ]
    if decoding_cases:
        lines.extend(["", "## Trajectory Decoding", ""])
        for case in decoding_cases:
            assert case.content_overlap is not None
            dec = case.content_overlap.decoding
            assert dec is not None
            details = [f"status `{dec.status.value}`", f"attempts {dec.attempt_count}"]
            if dec.action:
                details.append(f"route `{dec.action}`")
            if dec.failure_code:
                details.append(f"failure `{dec.failure_code.value}`")
            if dec.derived_files:
                details.append(f"derived files {len(dec.derived_files)}")
            lines.append(f"- **{case.scenario_id}**: {', '.join(details)}")
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
                                f"      - {name}: `{_safe_report_text(stream.value, 16_384)}`"
                            )
                if attempt.failure_code:
                    lines.append(f"    - Failure: `{attempt.failure_code.value}`")
    if result.errors:
        lines.extend(["", "## Errors", "", *[f"- {error}" for error in result.errors]])
    return "\n".join(lines) + "\n"
