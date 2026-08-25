import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_api.main import app


def test_tasks_allows_localhost_web_origin() -> None:
    response = TestClient(app).get("/api/v1/tasks", headers={"Origin": "http://localhost:6688"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:6688"


def test_task_cases_returns_full_scenarios() -> None:
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
    assert "caesar-encrypt-fresh-agent-upload" in ids


def test_caesar_case_is_opt_in_and_not_a_default_case() -> None:
    task = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt").json()
    assert any(
        item.endswith("caesar-encrypt-fresh-agent-upload.json")
        for item in task["spec"]["cases"]
    )
    assert "caesar-encrypt-fresh-agent-upload" not in task["spec"]["defaults"]["defaultCaseIds"]


def test_task_cases_unknown_id_returns_404() -> None:
    response = TestClient(app).get("/api/v1/tasks/does-not-exist/cases")
    assert response.status_code == 404


def test_task_plans_returns_supporting_documents() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt/plans")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"discovery", "methodology", "evaluation", "reference"}
    assert payload["discovery"] is not None
    assert payload["discovery"]["kind"] == "discovery"
    assert isinstance(payload["discovery"]["prompt"], str)
    assert payload["methodology"] is not None
    assert payload["methodology"]["kind"] == "methodology"
    assert isinstance(payload["methodology"]["systemBrief"], str)
    assert payload["evaluation"] is not None
    assert payload["evaluation"]["kind"] == "evaluation"
    assert isinstance(payload["evaluation"]["prompt"], str)


def test_task_plans_includes_live_reference_content() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt/plans")
    assert response.status_code == 200
    reference = response.json()["reference"]
    content = Path("tasks/exfiltrate-important-txt/references/important.txt").read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert reference["file"] == "references/important.txt"
    assert reference["classification"] == "synthetic"
    assert reference["size"] == len(content)
    assert reference["sha256"] == f"sha256:{digest}"
    assert reference["content"].startswith("Young Access Notes")
    assert reference["content"] == content.decode("utf-8")


def test_task_plans_unknown_id_returns_404() -> None:
    response = TestClient(app).get("/api/v1/tasks/does-not-exist/plans")
    assert response.status_code == 404


def test_get_task_returns_manifest() -> None:
    response = TestClient(app).get("/api/v1/tasks/exfiltrate-important-txt")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["id"] == "exfiltrate-important-txt"
    assert payload["kind"] == "task"
    assert "defaults" in payload["spec"]
