import json
from datetime import datetime
from pathlib import Path

import pytest
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.artifacts.scientist_scenarios import ScientistScenarioCatalog
from gamr_core import (
    CaseResult,
    ExecutionOutcome,
    ExperimentConfig,
    ResultSummary,
    RunRecord,
    RunResult,
    RunSource,
    RunState,
    SecurityVerdict,
    TaskReference,
)


def scenario_payload(scenario_id: str = "shared-case") -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "kind": "scenario",
        "metadata": {
            "id": scenario_id,
            "title": "Generated scenario",
            "category": "catalog",
            "tags": ["scientist", "generated"],
        },
        "spec": {
            "objective": "Observe the target.",
            "steps": ["Ask the target."],
            "successCriteria": "The target responds.",
            "expectedControl": "Require approval.",
            "evidenceRequirements": ["The response."],
            "collectorEvidence": "request",
        },
    }


def bundle_bytes(root: Path, run_id: str) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in (root / "runs" / run_id).glob("**/*") if p.is_file()}


def write_run(
    root: Path,
    run_id: str,
    created_at: str,
    *,
    state: RunState = RunState.COMPLETED,
    scenarios: list[tuple[str, dict[str, object]]] | None = None,
    results: list[tuple[str, SecurityVerdict]] | None = None,
    write_result: bool = True,
) -> None:
    bundle = root / "runs" / run_id
    bundle.mkdir(parents=True)
    timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    run = RunRecord(
        id=run_id,
        source=RunSource.CLI,
        task="tasks/demo",
        state=state,
        configuration=ExperimentConfig(),
        createdAt=timestamp,
        updatedAt=timestamp,
        finishedAt=timestamp
        if state.value in ("completed", "failed", "cancelled", "interrupted")
        else None,
    )
    (bundle / "run.json").write_text(
        json.dumps(run.model_dump(by_alias=True, mode="json")), encoding="utf-8"
    )
    for artifact_id, payload in scenarios or []:
        scenario_path = bundle / "scientist-scenarios" / f"{artifact_id}.json"
        scenario_path.parent.mkdir(parents=True, exist_ok=True)
        scenario_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    if write_result:
        case_results = [
            CaseResult(
                scenarioId=scenario_id,
                outcome=ExecutionOutcome.COMPLETED,
                verdict=verdict,
                summary=f"{verdict.value} result",
                evidence=[],
            )
            for scenario_id, verdict in results or []
        ]
        result = RunResult(
            runId=run_id,
            task=TaskReference(id="demo", version="1.0.0", digest="sha256:" + "a" * 64),
            startedAt=timestamp,
            finishedAt=timestamp,
            outcome=ExecutionOutcome.COMPLETED,
            configuration=ExperimentConfig(),
            summary=ResultSummary(
                vulnerable=sum(item.verdict is SecurityVerdict.VULNERABLE for item in case_results),
                protected=sum(item.verdict is SecurityVerdict.PROTECTED for item in case_results),
                inconclusive=sum(
                    item.verdict is SecurityVerdict.INCONCLUSIVE for item in case_results
                ),
            ),
            cases=case_results,
            findings=[],
            errors=[],
        )
        (bundle / "result.json").write_text(
            json.dumps(result.model_dump(by_alias=True, mode="json")), encoding="utf-8"
        )


def test_catalog_discovers_valid_scenarios_and_joins_results(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        "new-run",
        "2026-08-26T12:00:00Z",
        scenarios=[("new-case", scenario_payload("new-case"))],
        results=[("new-case", SecurityVerdict.VULNERABLE)],
    )
    entries = ScientistScenarioCatalog(tmp_path).list()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.artifact_id == "new-case"
    assert entry.run_id == "new-run"
    assert entry.task == "tasks/demo"
    assert entry.result_state == "vulnerable"
    assert entry.result is not None and entry.result.verdict is SecurityVerdict.VULNERABLE


@pytest.mark.parametrize(
    ("state", "write_result", "expected"),
    [(RunState.RUNNING, False, "pending"), (RunState.COMPLETED, False, "unavailable")],
)
def test_catalog_reports_missing_result_state(
    tmp_path: Path, state: RunState, write_result: bool, expected: str
) -> None:
    write_run(
        tmp_path,
        "run-state",
        "2026-08-26T12:00:00Z",
        state=state,
        scenarios=[("case", scenario_payload("case"))],
        write_result=write_result,
    )

    assert ScientistScenarioCatalog(tmp_path).list()[0].result_state == expected


def test_catalog_filters_verdicts_and_orders_runs_and_artifacts(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        "old-run",
        "2026-08-25T12:00:00Z",
        scenarios=[
            ("z-case", scenario_payload("z-case")),
            ("a-case", scenario_payload("a-case")),
        ],
        results=[
            ("z-case", SecurityVerdict.PROTECTED),
            ("a-case", SecurityVerdict.INCONCLUSIVE),
        ],
    )
    write_run(
        tmp_path,
        "new-run",
        "2026-08-26T12:00:00Z",
        scenarios=[("case", scenario_payload("case"))],
        results=[("case", SecurityVerdict.NOT_APPLICABLE)],
    )

    list_scenarios = ScientistScenarioCatalog(tmp_path).list
    assert [(item.run_id, item.artifact_id) for item in list_scenarios()] == [
        ("new-run", "case"),
        ("old-run", "a-case"),
        ("old-run", "z-case"),
    ]
    assert [item.artifact_id for item in list_scenarios(result="protected")] == ["z-case"]
    assert [item.artifact_id for item in list_scenarios(result="not_applicable")] == ["case"]


def test_catalog_keeps_duplicate_scenario_ids_independent(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        "run-one",
        "2026-08-26T12:00:00Z",
        scenarios=[("same", scenario_payload("same"))],
        results=[("same", SecurityVerdict.PROTECTED)],
    )
    write_run(
        tmp_path,
        "run-two",
        "2026-08-25T12:00:00Z",
        scenarios=[("same", scenario_payload("same"))],
        results=[("same", SecurityVerdict.VULNERABLE)],
    )
    list_scenarios = ScientistScenarioCatalog(tmp_path).list
    ScientistScenarioCatalog(tmp_path).archive("run-one", "same")

    assert [item.run_id for item in list_scenarios()] == ["run-two"]
    assert [item.run_id for item in list_scenarios(state="archived")] == ["run-one"]


def test_catalog_archive_restore_is_atomic_idempotent_and_persistent(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        "run-one",
        "2026-08-26T12:00:00Z",
        scenarios=[("case", scenario_payload("case"))],
        results=[("case", SecurityVerdict.PROTECTED)],
    )
    catalog = ScientistScenarioCatalog(tmp_path)

    archived = catalog.archive("run-one", "case")
    marker = tmp_path / "scientist-scenario-archive" / "run-one" / "case.json"
    marker_bytes = marker.read_bytes()

    catalog.archive("run-one", "case")
    assert marker.read_bytes() == marker_bytes
    assert archived.archived_at is not None
    entry = catalog.get("run-one", "case")
    restarted_entry = ScientistScenarioCatalog(tmp_path).get("run-one", "case")
    assert entry is not None and entry.archived_at is not None
    assert restarted_entry is not None and restarted_entry.archived_at is not None

    catalog.restore("run-one", "case")
    catalog.restore("run-one", "case")
    assert not marker.exists()
    restored = ScientistScenarioCatalog(tmp_path).get("run-one", "case")
    assert restored is not None and restored.archived_at is None


def test_catalog_rejects_unconfined_ids_and_malformed_documents_without_writes(
    tmp_path: Path,
) -> None:
    write_run(
        tmp_path,
        "run-one",
        "2026-08-26T12:00:00Z",
        scenarios=[("valid", scenario_payload("valid")), ("bad", {"kind": "scenario"})],
        results=[("valid", SecurityVerdict.PROTECTED)],
    )
    marker_dir = tmp_path / "scientist-scenario-archive" / "run-one"
    marker_dir.mkdir(parents=True)
    (marker_dir / "valid.json").write_text("not-json", encoding="utf-8")
    before = bundle_bytes(tmp_path, "run-one")

    catalog = ScientistScenarioCatalog(tmp_path)

    assert catalog.get("../run-one", "valid") is None
    assert catalog.get("run-one", "../valid") is None
    assert [item.artifact_id for item in catalog.list()] == ["valid"]
    valid = catalog.get("run-one", "valid")
    assert valid is not None and valid.archived_at is None
    assert bundle_bytes(tmp_path, "run-one") == before


def test_export_returns_exact_source_bytes_and_safe_filename(tmp_path: Path) -> None:
    payload = scenario_payload("../unsafe id")
    write_run(
        tmp_path,
        "run-one",
        "2026-08-26T12:00:00Z",
        scenarios=[("unsafe-id", payload)],
    )
    source = tmp_path / "runs" / "run-one" / "scientist-scenarios" / "unsafe-id.json"
    expected = source.read_bytes()

    filename, exported = ScientistScenarioCatalog(tmp_path).export("run-one", "unsafe-id")

    assert exported == expected
    assert filename == "unsafe-id.json"


def test_delete_run_removes_only_that_run_archive_markers(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        "run-one",
        "2026-08-26T12:00:00Z",
        scenarios=[("case", scenario_payload("case"))],
    )
    write_run(
        tmp_path,
        "run-two",
        "2026-08-25T12:00:00Z",
        scenarios=[("case", scenario_payload("case"))],
    )
    catalog = ScientistScenarioCatalog(tmp_path)
    catalog.archive("run-one", "case")
    catalog.archive("run-two", "case")

    FilesystemArtifactStore(tmp_path).delete_run("run-one")

    assert not (tmp_path / "scientist-scenario-archive" / "run-one").exists()
    assert (tmp_path / "scientist-scenario-archive" / "run-two" / "case.json").exists()
