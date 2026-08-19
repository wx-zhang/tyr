from fastapi.testclient import TestClient
from gamr_api.main import app


def test_datasets_allows_localhost_web_origin() -> None:
    response = TestClient(app).get("/api/v1/tasks", headers={"Origin": "http://localhost:6688"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:6688"


def test_dataset_cases_returns_full_scenarios() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt/cases")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    first = payload[0]
    assert first["kind"] == "scenario"
    assert "id" in first["metadata"] and "title" in first["metadata"]
    assert isinstance(first["spec"]["objective"], str)
    assert isinstance(first["spec"]["steps"], list)
    assert len(first["spec"]["steps"]) >= 1
    assert "expectedControl" in first["spec"]
    assert "evidenceRequirements" in first["spec"]
    ids = {item["metadata"]["id"] for item in payload}
    assert "rename-relocate-fresh-agent-upload" in ids


def test_dataset_cases_unknown_id_returns_404() -> None:
    response = TestClient(app).get("/api/v1/tasks/does-not-exist/cases")
    assert response.status_code == 404


def test_dataset_plans_returns_supporting_documents() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt/plans")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"discovery", "methodology", "evaluation"}
    assert payload["discovery"] is not None
    assert payload["discovery"]["kind"] == "discovery"
    assert isinstance(payload["discovery"]["prompt"], str)
    assert payload["methodology"] is not None
    assert payload["methodology"]["kind"] == "methodology"
    assert isinstance(payload["methodology"]["systemBrief"], str)
    assert payload["evaluation"] is not None
    assert payload["evaluation"]["kind"] == "evaluation"
    assert isinstance(payload["evaluation"]["prompt"], str)


def test_dataset_plans_unknown_id_returns_404() -> None:
    response = TestClient(app).get("/api/v1/tasks/does-not-exist/plans")
    assert response.status_code == 404


def test_get_task_returns_manifest() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["id"] == "exfiltrate-important-txt"
    assert payload["kind"] == "task"
    assert "defaults" in payload["spec"]
