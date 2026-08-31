import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adv_report_markdown import render_report

JsonObject = dict[str, Any]


def read_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object in {path}")
    return value


def text(value: object, fallback: str = "Unknown") -> str:
    return value if isinstance(value, str) and value else fallback




def scenario_record(data: JsonObject, source: str, source_path: Path) -> JsonObject:
    metadata = data.get("metadata")
    spec = data.get("spec")
    metadata = metadata if isinstance(metadata, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    scenario_id = text(metadata.get("id"), source_path.stem)
    requirements = spec.get("evidenceRequirements")
    steps = spec.get("steps")
    return {
        "id": scenario_id,
        "title": text(metadata.get("title"), scenario_id),
        "source": source,
        "objective": text(spec.get("objective"), "Not recorded."),
        "expected_control": text(spec.get("expectedControl"), "Not recorded."),
        "steps": steps if isinstance(steps, list) else [],
        "evidence_requirements": requirements if isinstance(requirements, list) else [],
    }


def task_identity(run_path: Path, run: JsonObject) -> tuple[str, str]:
    task_id = run.get("task")
    if isinstance(task_id, str) and task_id:
        return task_id, task_id
    dataset_id = run.get("dataset")
    if isinstance(dataset_id, str) and dataset_id:
        run_title = text(run.get("name"), dataset_id).split(" · ", maxsplit=1)[0]
        return dataset_id, run_title
    result_path = run_path / "result.json"
    if result_path.is_file():
        result_task = read_json(result_path).get("task")
        if isinstance(result_task, dict):
            task_id = text(result_task.get("id"), "unknown-task")
            return task_id, task_id
    snapshot_path = run_path / "task.snapshot.json"
    if snapshot_path.is_file():
        snapshot = read_json(snapshot_path)
        manifest = snapshot.get("manifest")
        manifest = manifest if isinstance(manifest, dict) else {}
        metadata = manifest.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        task_id = text(metadata.get("id"), "unknown-task")
        return task_id, text(metadata.get("title"), task_id)
    return "unknown-task", "Unknown task"


def add_task_scenarios(root: Path, tasks: dict[str, JsonObject]) -> None:
    task_root = root / "tasks"
    if not task_root.is_dir():
        raise RuntimeError(f"Task directory does not exist: {task_root}")
    for manifest_path in sorted(task_root.glob("*/task.json")):
        manifest = read_json(manifest_path)
        metadata = manifest.get("metadata")
        spec = manifest.get("spec")
        metadata = metadata if isinstance(metadata, dict) else {}
        spec = spec if isinstance(spec, dict) else {}
        task_id = text(metadata.get("id"), manifest_path.parent.name)
        task = tasks.setdefault(
            task_id,
            {"id": task_id, "title": text(metadata.get("title"), task_id), "scenarios": {}},
        )
        scenario_paths = spec.get("scenarios")
        if not isinstance(scenario_paths, list):
            continue
        for relative_path in scenario_paths:
            if not isinstance(relative_path, str):
                continue
            path = manifest_path.parent / relative_path
            scenario = scenario_record(read_json(path), "Authored task", path)
            task["scenarios"][scenario["id"]] = scenario


def add_snapshot_scenarios(run_path: Path, task: JsonObject) -> None:
    for snapshot_path in (
        run_path / "task.snapshot.json",
        run_path / "dataset.snapshot.json",
    ):
        if not snapshot_path.is_file():
            continue
        snapshot_scenarios = read_json(snapshot_path).get("scenarios")
        if not isinstance(snapshot_scenarios, list):
            continue
        for value in snapshot_scenarios:
            if not isinstance(value, dict):
                continue
            scenario = scenario_record(value, "Run snapshot", snapshot_path)
            task["scenarios"].setdefault(scenario["id"], scenario)


def result_timestamp(result: JsonObject, run: JsonObject) -> str:
    for key in ("occurredAt", "finishedAt", "updatedAt", "createdAt"):
        value = result.get(key) if key == "occurredAt" else run.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def collect_run_results(run_path: Path, run: JsonObject) -> list[tuple[JsonObject, Path]]:
    result_paths = sorted((run_path / "scenario-execution-results").glob("*.json"))
    if result_paths:
        return [(read_json(path), path) for path in result_paths]
    final_path = run_path / "result.json"
    if not final_path.is_file():
        return []
    final_result = read_json(final_path)
    executions = final_result.get("scenarioExecutions")
    if not isinstance(executions, list):
        executions = final_result.get("cases")
    if not isinstance(executions, list):
        return []
    return [(value, final_path) for value in executions if isinstance(value, dict)]


def archived_scenario_ids(root: Path) -> set[str]:
    archive = root / ".gamr/scientist-scenario-archive"
    if not archive.is_dir():
        return set()
    scenario_ids: set[str] = set()
    for path in sorted(archive.glob("*/*.json")):
        scenario_id = read_json(path).get("scenarioId")
        if isinstance(scenario_id, str) and scenario_id:
            scenario_ids.add(scenario_id)
    return scenario_ids


def add_runs(root: Path, tasks: dict[str, JsonObject], archived_ids: set[str]) -> None:
    runs_root = root / ".gamr/runs"
    if not runs_root.is_dir():
        return
    for run_path in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        run_file = run_path / "run.json"
        if not run_file.is_file():
            continue
        run = read_json(run_file)
        task_id, task_title = task_identity(run_path, run)
        task = tasks.setdefault(
            task_id,
            {"id": task_id, "title": task_title, "scenarios": {}},
        )
        add_snapshot_scenarios(run_path, task)
        researcher_ids: set[str] = set()
        for path in sorted((run_path / "scientist-scenarios").glob("*.json")):
            scenario = scenario_record(read_json(path), "Adversarial Researcher", path)
            if scenario["id"] in archived_ids:
                continue
            researcher_ids.add(scenario["id"])
            existing = task["scenarios"].get(scenario["id"])
            if existing is None or existing["source"] == "Run snapshot":
                task["scenarios"][scenario["id"]] = scenario
        for result, result_path in collect_run_results(run_path, run):
            scenario_id = text(result.get("scenarioId"), "unknown-scenario")
            existing = task["scenarios"].get(scenario_id)
            if scenario_id in archived_ids and (
                existing is None or existing["source"] != "Authored task"
            ):
                continue
            scenario = task["scenarios"].setdefault(
                scenario_id,
                {
                    "id": scenario_id,
                    "title": scenario_id,
                    "source": (
                        "Adversarial Researcher"
                        if scenario_id in researcher_ids or result.get("stage") == "scientist"
                        else "Observed run"
                    ),
                    "objective": "Not recorded.",
                    "expected_control": "Not recorded.",
                    "steps": [],
                    "evidence_requirements": [],
                },
            )
            candidate = {
                "data": result,
                "path": result_path,
                "run_id": text(run.get("id"), run_path.name),
                "timestamp": result_timestamp(result, run),
                "run_path": run_path,
            }
            current = scenario.get("result")
            if not isinstance(current, dict) or candidate["timestamp"] > current["timestamp"]:
                scenario["result"] = candidate





def generate_report(
    root: Path,
    *,
    generated_at: datetime | None = None,
    report_id: str | None = None,
    include_without_results: bool = False,
) -> Path:
    root = root.resolve()
    generated_at = generated_at or datetime.now(UTC)
    report_id = report_id or uuid.uuid4().hex[:8]
    tasks: dict[str, JsonObject] = {}
    add_task_scenarios(root, tasks)
    add_runs(root, tasks, archived_scenario_ids(root))
    if not include_without_results:
        for task in tasks.values():
            task["scenarios"] = {
                key: scenario
                for key, scenario in task["scenarios"].items()
                if "result" in scenario
            }
        tasks = {key: task for key, task in tasks.items() if task["scenarios"]}
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = root / ".gamr/reports" / f"{timestamp}_{report_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(tasks, report_path, generated_at), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the GAMR adversarial scenario report.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="GAMR repository root")
    parser.add_argument(
        "--include-without-results",
        action="store_true",
        help="include scenarios without a Scenario Execution result",
    )
    arguments = parser.parse_args()
    print(
        generate_report(
            arguments.root,
            include_without_results=arguments.include_without_results,
        )
    )
