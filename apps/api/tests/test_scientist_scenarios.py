import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_settings
from gamr_api.main import app
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


def write_bundle(
    root: Path,
    run_id: str,
    created_at: str,
    scenario_id: str,
    verdict: SecurityVerdict,
) -> Path:
    bundle = root / "runs" / run_id
    bundle.mkdir(parents=True)
    timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    run = RunRecord(
        id=run_id,
        source=RunSource.CLI,
        task="tasks/demo",
        state=RunState.COMPLETED,
        configuration=ExperimentConfig(),
        createdAt=timestamp,
        updatedAt=timestamp,
        finishedAt=timestamp,
    )
    (bundle / "run.json").write_text(
        json.dumps(run.model_dump(by_alias=True, mode="json")), encoding="utf-8"
    )
    scenario = {
        "schemaVersion": "1.0",
        "kind": "scenario",
        "metadata": {"id": scenario_id, "title": "Generated", "tags": ["scientist"]},
        "spec": {
            "objective": "Observe.",
            "steps": ["Ask."],
            "successCriteria": "Respond.",
            "expectedControl": "Protect.",
            "evidenceRequirements": ["Response."],
        },
    }
    source = bundle / "scientist-scenarios" / f"{scenario_id}.json"
    source.parent.mkdir()
    source.write_text(json.dumps(scenario, separators=(",", ":")), encoding="utf-8")
    case = CaseResult(
        scenarioId=scenario_id,
        outcome=ExecutionOutcome.COMPLETED,
        verdict=verdict,
        summary="Result.",
        evidence=[],
    )
    result = RunResult(
        runId=run_id,
        task=TaskReference(id="demo", version="1.0.0", digest="sha256:" + "a" * 64),
        startedAt=timestamp,
        finishedAt=timestamp,
        outcome=ExecutionOutcome.COMPLETED,
        configuration=ExperimentConfig(),
        summary=ResultSummary(vulnerable=1, protected=0, inconclusive=0),
        cases=[case],
        findings=[],
        errors=[],
    )
    (bundle / "result.json").write_text(
        json.dumps(result.model_dump(by_alias=True, mode="json")), encoding="utf-8"
    )
    return source


def client_for(root: Path) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(root))
    return TestClient(app)


def test_catalog_lists_views_filters_and_origin_fields(tmp_path: Path) -> None:
    write_bundle(tmp_path, "old-run", "2026-08-25T12:00:00Z", "old", SecurityVerdict.PROTECTED)
    source = write_bundle(
        tmp_path, "new-run", "2026-08-26T12:00:00Z", "new", SecurityVerdict.VULNERABLE
    )
    client = client_for(tmp_path)
    try:
        active = client.get("/api/v1/scientist-scenarios")
        protected = client.get("/api/v1/scientist-scenarios?result=protected")
        archived = client.get("/api/v1/scientist-scenarios?state=archived")
    finally:
        app.dependency_overrides.clear()

    assert active.status_code == 200
    assert [item["artifactId"] for item in active.json()] == ["new", "old"]
    assert active.json()[0]["scenario"]["spec"]["successCriteria"] == "Respond."
    assert active.json()[0]["runId"] == "new-run"
    assert active.json()[0]["result"]["verdict"] == "vulnerable"
    assert [item["artifactId"] for item in protected.json()] == ["old"]
    assert archived.json() == []
    assert source.read_bytes()


def test_catalog_archive_restore_and_export_are_safe_and_idempotent(tmp_path: Path) -> None:
    source = write_bundle(
        tmp_path, "run-one", "2026-08-26T12:00:00Z", "case", SecurityVerdict.PROTECTED
    )
    before = source.read_bytes()
    client = client_for(tmp_path)
    try:
        archive = client.put("/api/v1/scientist-scenarios/run-one/case/archive")
        repeat = client.put("/api/v1/scientist-scenarios/run-one/case/archive")
        export = client.get("/api/v1/scientist-scenarios/run-one/case/export")
        restore = client.delete("/api/v1/scientist-scenarios/run-one/case/archive")
        missing = client.get("/api/v1/scientist-scenarios/nope/case/export")
    finally:
        app.dependency_overrides.clear()

    assert archive.status_code == repeat.status_code == restore.status_code == 200
    assert archive.json()["archivedAt"] == repeat.json()["archivedAt"]
    assert export.status_code == 200
    assert export.content == before
    assert export.headers["content-type"].startswith("application/json")
    assert export.headers["content-disposition"] == 'attachment; filename="case.json"'
    assert restore.json()["archivedAt"] is None
    assert missing.status_code == 404
    assert source.read_bytes() == before
