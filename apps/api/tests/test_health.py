from fastapi.testclient import TestClient
from gamr_api.main import app


def test_health() -> None:
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}
