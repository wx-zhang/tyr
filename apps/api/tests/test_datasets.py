from fastapi.testclient import TestClient
from gamr_api.main import app


def test_datasets_allows_localhost_web_origin() -> None:
    response = TestClient(app).get(
        "/api/v1/datasets", headers={"Origin": "http://localhost:6688"}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:6688"


def test_dataset_cases_returns_scenario_ids_and_titles() -> None:
    response = TestClient(app).get("/api/v1/datasets/first-plan/cases")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    first = payload[0]
    assert "id" in first and "title" in first
    ids = {item["id"] for item in payload}
    assert "rename-relocate-fresh-agent-upload" in ids


def test_dataset_cases_unknown_id_returns_404() -> None:
    response = TestClient(app).get("/api/v1/datasets/does-not-exist/cases")
    assert response.status_code == 404
