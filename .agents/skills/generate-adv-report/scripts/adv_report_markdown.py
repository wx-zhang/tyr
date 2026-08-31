from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


def text(value: object, fallback: str = "Unknown") -> str:
    return value if isinstance(value, str) and value else fallback


def markdown(value: object, fallback: str = "Unknown") -> str:
    escaped = text(value, fallback).replace("\n", " ").replace("\r", " ")
    for character in "\\`*_[]<>#|":
        escaped = escaped.replace(character, f"\\{character}")
    return " ".join(escaped.split())


def relative_link(report_path: Path, target: Path) -> str:
    return f"../{target.relative_to(report_path.parent.parent).as_posix()}"


def render_result(report_path: Path, result: JsonObject) -> list[str]:
    data = result["data"]
    run_path = result["run_path"]
    lines = [
        f"**Latest result:** {markdown(data.get('verdict'))}",
        "",
        f"- Run: `{markdown(result['run_id'])}`",
        f"- Scenario Execution: `{markdown(data.get('scenarioExecutionId'))}`",
        f"- Recorded at: {markdown(result['timestamp'], 'Not recorded')}",
        f"- Completion outcome: {markdown(data.get('outcome'))}",
        f"- Objective status: {markdown(data.get('objectiveStatus'))}",
        f"- Assessment status: {markdown(data.get('assessmentStatus'))}",
        f"- Summary: {markdown(data.get('summary'), 'Not recorded.')}",
    ]
    reason_codes = data.get("reasonCodes")
    if isinstance(reason_codes, list) and reason_codes:
        rendered_codes = ", ".join(f"`{markdown(code)}`" for code in reason_codes)
        lines.append(f"- Reason codes: {rendered_codes}")
    missing = data.get("missingEvidence")
    if isinstance(missing, list) and missing:
        lines.extend(["", "**Missing evidence:**", ""])
        lines.extend(f"- {markdown(item)}" for item in missing)
    lines.extend(["", "**Run evidence:**", ""])
    evidence_targets = [("Scenario result", result["path"])]
    final_result = run_path / "result.json"
    if final_result.is_file() and final_result != result["path"]:
        evidence_targets.append(("Run result", final_result))
    run_report = run_path / "report.md"
    if run_report.is_file():
        evidence_targets.append(("Run report", run_report))
    evidence = data.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            artifact = item.get("artifact")
            if isinstance(artifact, str) and artifact:
                label = f"Turn {text(item.get('turnId'), 'unknown')}"
                evidence_targets.append((label, run_path / artifact))
    for label, target in evidence_targets:
        lines.append(f"- [{markdown(label)}]({relative_link(report_path, target)})")
    return lines


def render_scenario(report_path: Path, scenario: JsonObject) -> list[str]:
    lines = [
        "",
        f"### {markdown(scenario['title'])}",
        "",
        f"- Scenario ID: `{markdown(scenario['id'])}`",
        f"- **Source:** {markdown(scenario['source'])}",
        f"- Objective: {markdown(scenario['objective'])}",
        "",
        "**Steps:**",
        "",
    ]
    steps = scenario["steps"]
    lines.extend(
        [f"{index}. {markdown(step)}" for index, step in enumerate(steps, start=1)]
        if steps
        else ["1. Not recorded."]
    )
    lines.extend(
        [
            "",
            f"**Expected control:** {markdown(scenario['expected_control'])}",
            "",
            "**Evidence requirements:**",
            "",
        ]
    )
    requirements = scenario["evidence_requirements"]
    lines.extend(
        [f"- {markdown(item)}" for item in requirements]
        if requirements
        else ["- Not recorded."]
    )
    lines.append("")
    result = scenario.get("result")
    if isinstance(result, dict):
        lines.extend(render_result(report_path, result))
    else:
        lines.append("**Latest result:** No Scenario Execution result found.")
    return lines


def render_report(tasks: dict[str, JsonObject], report_path: Path, generated_at: datetime) -> str:
    scenario_count = sum(len(task["scenarios"]) for task in tasks.values())
    lines = [
        "# Adversarial Scenario Report",
        "",
        f"Generated at {generated_at.astimezone(UTC).isoformat().replace('+00:00', 'Z')}.",
        "",
        f"- {len(tasks)} tasks",
        f"- {scenario_count} scenarios with a Scenario Execution result",
        "",
        "The result shown for each scenario is the newest available Scenario Execution result by "
        "`occurredAt`, with the run timestamp used when `occurredAt` is absent.",
    ]
    for task_id in sorted(tasks):
        task = tasks[task_id]
        lines.extend(["", f"## {markdown(task['title'])}", "", f"Task ID: `{markdown(task_id)}`"])
        for scenario_id in sorted(task["scenarios"]):
            lines.extend(render_scenario(report_path, task["scenarios"][scenario_id]))
    return "\n".join(lines) + "\n"
