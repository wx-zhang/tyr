from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import ExperimentConfig, RunState
from gamr_engine.collector_verification import CollectorFile, CollectorVerification


def _client(tmp_path: Path) -> TestClient:
    root = tmp_path / "runs" / "run-1" / "collector-verifications"
    root.mkdir(parents=True)
    (root / "case.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "caseId": "case-1",
                "requirement": "file",
                "status": "verified",
                "requests": [
                    {
                        "request_id": "0123456789abcdef0123456789abcdef",
                        "requirement": "file",
                        "status": "verified",
                        "files": [
                            {
                                "file_id": "file-1",
                                "filename": "evidence.txt",
                                "content_type": "text/plain",
                                "size": 8,
                                "sha256": "a" * 64,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={
            "run-1": RunRecord(
                id="run-1",
                experiment_id="experiment-1",
                task="fixture",
                state=RunState.COMPLETED,
                configuration=ExperimentConfig(),
                created_at=datetime.now(UTC),
            ),
            "run-2": RunRecord(
                id="run-2",
                experiment_id="experiment-1",
                task="fixture",
                state=RunState.COMPLETED,
                configuration=ExperimentConfig(),
                created_at=datetime.now(UTC),
            ),
        }
    )
    settings = Settings(
        artifact_root=str(tmp_path),
        collector_username="admin",
        collector_password="secret",
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_lists_only_safe_collector_metadata(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        response = client.get("/api/v1/runs/run-1/collector-verifications")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["files"][0]["downloadAvailable"] is True
    assert "secret" not in response.text


def test_download_requires_file_to_belong_to_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeCollector:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def download(self, _file: object) -> bytes:
            return b"evidence"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("gamr_api.routes.collector_artifacts.CollectorClient", FakeCollector)
    client = _client(tmp_path)
    try:
        missing = client.get("/api/v1/runs/run-2/collector-files/file-1/download")
        response = client.get("/api/v1/runs/run-1/collector-files/file-1/download")
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 404
    assert response.status_code == 200
    assert response.content == b"evidence"
    assert response.headers["content-disposition"] == 'attachment; filename="evidence.txt"'
    assert response.headers["cache-control"] == "no-store"


def test_previews_verified_text_with_safe_inline_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeCollector:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def download(self, _file: object) -> bytes:
            return b"# Evidence\n\nVerified text."

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("gamr_api.routes.collector_artifacts.CollectorClient", FakeCollector)
    client = _client(tmp_path)
    try:
        response = client.get("/api/v1/runs/run-1/collector-files/file-1/preview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "# Evidence\n\nVerified text."
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == 'inline; filename="evidence.txt"'
    assert response.headers["x-content-type-options"] == "nosniff"


def test_hydrates_and_previews_verified_request_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"<delivery>fake data</delivery>"
    body_file = CollectorFile(
        "body-0123456789abcdef0123456789abcdef",
        "request-body.xml",
        "application/xml",
        len(body),
        "b" * 64,
    )

    class FakeCollector:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def verify(self, request_id: str, _requirement: str) -> CollectorVerification:
            return CollectorVerification(request_id, "request", "verified", [body_file])

        async def download(self, _file: object) -> bytes:
            return body

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("gamr_api.routes.collector_artifacts.CollectorClient", FakeCollector)
    client = _client(tmp_path)
    manifest = tmp_path / "runs" / "run-1" / "collector-verifications" / "case.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["requirement"] = "request"
    payload["requests"][0]["requirement"] = "request"
    payload["requests"][0]["files"] = []
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    try:
        listed = client.get("/api/v1/runs/run-1/collector-verifications")
        preview = client.get(
            "/api/v1/runs/run-1/collector-files/body-0123456789abcdef0123456789abcdef/preview"
        )
    finally:
        app.dependency_overrides.clear()

    assert listed.json()[0]["files"][0]["filename"] == "request-body.xml"
    assert preview.status_code == 200
    assert preview.content == body


def test_recovers_files_for_existing_failed_exact_request_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovered = CollectorFile(
        "recovered-file",
        "chunked_upload_demo.txt",
        "text/plain",
        8,
        "c" * 64,
    )

    class FakeCollector:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def verify(self, request_id: str, requirement: str) -> CollectorVerification:
            assert requirement == "file"
            return CollectorVerification(request_id, "file", "verified", [recovered])

        async def download(self, _file: object) -> bytes:
            return b"evidence"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("gamr_api.routes.collector_artifacts.CollectorClient", FakeCollector)
    client = _client(tmp_path)
    manifest = tmp_path / "runs" / "run-1" / "collector-verifications" / "case.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    payload["requests"][0]["status"] = "failed"
    payload["requests"][0]["files"] = []
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    try:
        listed = client.get("/api/v1/runs/run-1/collector-verifications")
        downloaded = client.get("/api/v1/runs/run-1/collector-files/recovered-file/download")
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()[0]["files"][0]["filename"] == "chunked_upload_demo.txt"
    assert downloaded.status_code == 200
    assert downloaded.content == b"evidence"


def test_previews_verified_raster_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCollector:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def download(self, _file: object) -> bytes:
            return b"png"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("gamr_api.routes.collector_artifacts.CollectorClient", FakeCollector)
    client = _client(tmp_path)
    manifest = tmp_path / "runs" / "run-1" / "collector-verifications" / "case.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["requests"][0]["files"][0]["filename"] = "evidence.png"
    payload["requests"][0]["files"][0]["content_type"] = "image/png"
    payload["requests"][0]["files"][0]["size"] = 3
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    try:
        response = client.get("/api/v1/runs/run-1/collector-files/file-1/preview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == b"png"
    assert response.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    ("content_type", "size", "status_code"),
    [
        ("application/pdf", 8, 415),
        ("text/plain", 5 * 1024 * 1024 + 1, 413),
    ],
)
def test_preview_rejects_unsupported_or_oversized_files(
    tmp_path: Path, content_type: str, size: int, status_code: int
) -> None:
    client = _client(tmp_path)
    manifest = tmp_path / "runs" / "run-1" / "collector-verifications" / "case.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["requests"][0]["files"][0]["content_type"] = content_type
    payload["requests"][0]["files"][0]["size"] = size
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    try:
        response = client.get("/api/v1/runs/run-1/collector-files/file-1/preview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status_code
