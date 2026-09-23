from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from gamr_adapters.benign_config import BenignSettings
from gamr_adapters.benign_model import BenignGenerationError, BenignModel
from gamr_api.main import create_app
from gamr_api.routes.benign import get_benign_settings


def test_unconfirmed_action_rejected_and_empty_index(tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_benign_settings] = lambda: BenignSettings(root=tmp_path)
    client = TestClient(app)
    assert client.get("/api/v1/benign/runs").json() == []
    result = client.post(
        "/api/v1/benign/runs",
        json={
            "scenarios": [],
            "action_mode": "approval_required",
            "confirmed": False,
        },
    )
    assert result.status_code == 422


def test_missing_run_does_not_create_artifacts(tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_benign_settings] = lambda: BenignSettings(root=tmp_path)
    client = TestClient(app)
    assert client.get("/api/v1/benign/runs/missing").status_code == 404
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize(
    "status,detail",
    [
        (502, "Model reached its token limit"),
        (504, "Model generation timed out"),
    ],
)
def test_model_failure_is_a_readable_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    detail: str,
) -> None:
    async def fail(*args: Any, **kwargs: Any) -> Any:
        raise BenignGenerationError(detail, status)

    monkeypatch.setattr(BenignModel, "draft", fail)
    app = create_app()
    app.dependency_overrides[get_benign_settings] = lambda: BenignSettings(root=tmp_path)
    response = TestClient(app).post(
        "/api/v1/benign/drafts",
        json={
            "text": "Invite Dorian",
            "workspace": "mira",
            "timezone": "UTC",
        },
    )
    assert response.status_code == status
    assert response.json() == {"detail": detail}
