import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType


def load_helper() -> ModuleType:
    helper_path = (
        Path(__file__).parents[2]
        / ".agents/skills/generate-adv-report/scripts/generate_report.py"
    )
    spec = importlib.util.spec_from_file_location("generate_adv_report", helper_path)
    assert spec is not None
    sys.path.insert(0, str(helper_path.parent))
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_task(root: Path, scenario_id: str, title: str) -> None:
    task = root / "tasks/example-task"
    write_json(
        task / "task.json",
        {
            "metadata": {"id": "example-task", "title": "Example task", "version": "1.0"},
            "spec": {"scenarios": [f"cases/{scenario_id}.json"]},
        },
    )
    write_json(
        task / f"cases/{scenario_id}.json",
        {
            "metadata": {"id": scenario_id, "title": title},
            "spec": {
                "objective": f"Objective for {title}",
                "steps": [f"Execute the step for {title}", "Record the outcome"],
                "expectedControl": f"Control for {title}",
                "evidenceRequirements": ["Retained raw operation evidence"],
            },
        },
    )


def write_run(
    root: Path,
    run_id: str,
    occurred_at: str,
    scenario_id: str,
    verdict: str,
    summary: str,
    *,
    researcher: bool = False,
) -> None:
    run = root / ".gamr/runs" / run_id
    write_json(
        run / "run.json",
        {
            "id": run_id,
            "task": "example-task",
            "state": "completed",
            "createdAt": occurred_at,
            "finishedAt": occurred_at,
        },
    )
    write_json(
        run / "scenario-execution-results" / f"{run_id}-execution.json",
        {
            "scenarioId": scenario_id,
            "scenarioExecutionId": f"{run_id}-execution",
            "outcome": "completed",
            "objectiveStatus": "achieved" if verdict == "vulnerable" else "not_achieved",
            "verdict": verdict,
            "summary": summary,
            "evidence": [{"turnId": f"{run_id}-turn", "artifact": f"raw/{run_id}.json"}],
            "assessmentStatus": "valid",
            "reasonCodes": [f"{verdict}_reason"],
            "missingEvidence": ["Missing approval record"] if verdict == "inconclusive" else [],
            "stage": "scientist" if researcher else "test",
            "occurredAt": occurred_at,
        },
    )
    write_json(run / "raw" / f"{run_id}.json", {"evidence": run_id})
    if researcher:
        write_json(
            run / "scientist-scenarios" / f"{scenario_id}.json",
            {
                "metadata": {"id": scenario_id, "title": "Researcher scenario"},
                "spec": {
                    "objective": "Researcher objective",
                    "steps": ["Propose a new attack", "Capture researcher evidence"],
                    "expectedControl": "Researcher control",
                    "evidenceRequirements": ["Researcher evidence"],
                },
            },
        )


def test_report_uses_latest_result_and_includes_researcher_scenarios(tmp_path: Path) -> None:
    write_task(tmp_path, "canonical", "Canonical scenario")
    write_run(
        tmp_path,
        "old-run",
        "2026-08-27T10:00:00Z",
        "canonical",
        "vulnerable",
        "Old result",
    )
    write_run(
        tmp_path,
        "new-run",
        "2026-08-28T10:00:00Z",
        "canonical",
        "protected",
        "Latest result",
    )
    write_run(
        tmp_path,
        "research-run",
        "2026-08-28T11:00:00Z",
        "researcher-case",
        "inconclusive",
        "Research result",
        researcher=True,
    )
    write_run(
        tmp_path,
        "observed-run",
        "2026-08-28T11:30:00Z",
        "observed-only",
        "protected",
        "Observed result",
    )
    write_run(
        tmp_path,
        "archive-run",
        "2026-08-28T11:45:00Z",
        "archived-case",
        "protected",
        "Archived result",
        researcher=True,
    )
    write_json(
        tmp_path / ".gamr/scientist-scenario-archive/archive-run/archived-case.json",
        {
            "runId": "archive-run",
            "scenarioId": "archived-case",
            "title": "Archived scenario must not appear",
        },
    )

    report = load_helper().generate_report(
        tmp_path,
        generated_at=datetime(2026, 8, 28, 12, 30, tzinfo=UTC),
        report_id="a1b2c3d4",
    )
    content = report.read_text(encoding="utf-8")

    assert report == tmp_path / ".gamr/reports/20260828T123000Z_a1b2c3d4.md"
    assert "# Adversarial Scenario Report" in content
    assert "## Example task" in content
    assert "### Canonical scenario" in content
    assert "Latest result" in content
    assert "Old result" not in content
    assert "**Source:** Authored task" in content
    assert "### Researcher scenario" in content
    assert "**Source:** Adversarial Researcher" in content
    assert "Research result" in content
    assert "1. Propose a new attack" in content
    assert "2. Capture researcher evidence" in content
    assert "Archived scenario must not appear" not in content
    assert "`archived-case`" not in content
    assert "Archived result" not in content
    assert "### observed-only" in content
    assert "1. Not recorded." in content
    assert "../runs/research-run/raw/research-run.json" in content
    assert "Missing approval record" in content
    assert "3 scenarios" in content


def test_scenarios_without_results_require_explicit_inclusion(tmp_path: Path) -> None:
    write_task(tmp_path, "never-run", "Never run")

    default_report = load_helper().generate_report(
        tmp_path,
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        report_id="11223344",
    )
    default_content = default_report.read_text(encoding="utf-8")
    assert "### Never run" not in default_content
    assert "0 scenarios with a Scenario Execution result" in default_content

    report = load_helper().generate_report(
        tmp_path,
        generated_at=datetime(2026, 8, 28, 0, 1, tzinfo=UTC),
        report_id="55667788",
        include_without_results=True,
    )
    content = report.read_text(encoding="utf-8")

    assert "### Never run" in content
    assert "**Latest result:** No Scenario Execution result found." in content
    assert "**Evidence requirements:**" in content
    assert "Retained raw operation evidence" in content
    assert "**Steps:**" in content
    assert "1. Execute the step for Never run" in content
    assert "2. Record the outcome" in content


def test_legacy_dataset_results_are_collected(tmp_path: Path) -> None:
    write_task(tmp_path, "current", "Current scenario")
    run = tmp_path / ".gamr/runs/legacy-run"
    write_json(
        run / "run.json",
        {
            "id": "legacy-run",
            "dataset": "first-plan",
            "name": "First Plan · 12 Aug 2026",
            "finishedAt": "2026-08-12T15:02:40Z",
        },
    )
    write_json(
        run / "scientist-scenarios/legacy-research.json",
        {
            "metadata": {"id": "legacy-research", "title": "Legacy research"},
            "spec": {
                "objective": "Legacy objective",
                "steps": ["Run legacy step"],
                "expectedControl": "Legacy control",
                "evidenceRequirements": ["Legacy evidence"],
            },
        },
    )
    write_json(
        run / "result.json",
        {
            "cases": [
                {
                    "scenarioId": "legacy-research",
                    "outcome": "completed",
                    "objectiveStatus": "partial",
                    "verdict": "inconclusive",
                    "summary": "Legacy result",
                    "evidence": [
                        {"turnId": "legacy-turn", "artifact": "raw/legacy.json"}
                    ],
                }
            ]
        },
    )
    write_json(run / "raw/legacy.json", {"evidence": "legacy"})

    report = load_helper().generate_report(
        tmp_path,
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        report_id="99aabbcc",
    )
    content = report.read_text(encoding="utf-8")

    assert "## First Plan" in content
    assert "### Legacy research" in content
    assert "Legacy result" in content
    assert "../runs/legacy-run/raw/legacy.json" in content
