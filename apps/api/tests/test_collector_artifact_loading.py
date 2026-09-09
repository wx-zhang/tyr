from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import HTTPException
from gamr_adapters.config import Settings
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_api.routes import collector_artifacts as routes
from gamr_core import ExperimentConfig, RunState
from gamr_engine.collector_verification import CollectorFile, CollectorVerification


@pytest.fixture
def collector_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Settings, InMemoryRegistry, Path]:
    monkeypatch.setattr(routes, "_REMOTE_FILES_CACHE", {})
    root = tmp_path / "runs" / "run-1" / "collector-verifications"
    root.mkdir(parents=True)
    settings = Settings(
        artifact_root=str(tmp_path), collector_username="admin", collector_password="secret"
    )
    registry = InMemoryRegistry(
        runs={
            run_id: RunRecord(
                id=run_id,
                experiment_id="experiment-1",
                task="fixture",
                state=RunState.COMPLETED,
                configuration=ExperimentConfig(),
                created_at=datetime.now(UTC),
            )
            for run_id in ("run-1", "run-2")
        }
    )
    return settings, registry, root


def _manifest(root: Path, name: str, requests: list[dict[str, Any]]) -> None:
    (root / f"{name}.json").write_text(
        json.dumps(
            {"caseId": name, "requirement": "file", "status": "verified", "requests": requests}
        ),
        encoding="utf-8",
    )


def _persisted_request() -> dict[str, Any]:
    return {
        "request_id": "a" * 32,
        "requirement": "file",
        "status": "verified",
        "files": [
            {
                "file_id": "known-file",
                "filename": "evidence.txt",
                "content_type": "text/plain",
                "size": 8,
                "sha256": "a" * 64,
            }
        ],
    }


async def test_preview_uses_persisted_metadata_before_any_remote_recovery(
    collector_run: tuple[Settings, InMemoryRegistry, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, registry, root = collector_run
    unresolved = {"request_id": "b" * 32, "requirement": "request", "files": []}
    _manifest(root, "a-unrelated", [unresolved])
    _manifest(root, "b-known", [unresolved, _persisted_request()])

    class FakeCollector:
        def __init__(self, *_args: object) -> None:
            pass

        async def verify(self, *_args: object) -> CollectorVerification:
            pytest.fail("Persisted preview must not wait for unrelated metadata recovery")

        async def download(self, file: CollectorFile) -> bytes:
            assert file.file_id == "known-file"
            return b"evidence"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(routes, "CollectorClient", FakeCollector)
    response = await routes.collector_file_preview("run-1", "known-file", registry, settings)
    assert response.body == b"evidence"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("run_id", "file_id", "request_status", "size"),
    [
        ("missing-run", "known-file", "verified", 8),
        ("run-2", "known-file", "verified", 8),
        ("run-1", "unknown-file", "verified", 8),
        ("run-1", "known-file", "failed", 8),
        ("run-1", "known-file", "verified", "8"),
    ],
)
async def test_preview_denies_unowned_unverified_or_invalid_metadata(
    collector_run: tuple[Settings, InMemoryRegistry, Path],
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
    file_id: str,
    request_status: str,
    size: int | str,
) -> None:
    settings, registry, root = collector_run
    request = _persisted_request()
    request["status"] = request_status
    request["files"][0]["size"] = size
    _manifest(root, "known", [request])

    def forbidden_client(*_args: object) -> None:
        pytest.fail("Denied metadata must not reach the collector")

    monkeypatch.setattr(routes, "CollectorClient", forbidden_client)
    with pytest.raises(HTTPException) as error:
        await routes.collector_file_preview(run_id, file_id, registry, settings)
    assert error.value.status_code == 404


async def test_listing_bounds_remote_work_preserves_order_and_caches_recovery(
    collector_run: tuple[Settings, InMemoryRegistry, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, registry, root = collector_run
    request_ids = [f"{index:032x}" for index in range(6)]
    for index, request_id in enumerate(request_ids):
        _manifest(
            root,
            f"case-{index}",
            [{"request_id": request_id, "requirement": "file", "status": "failed", "files": []}],
        )
    original = {path.name: path.read_bytes() for path in root.glob("*.json")}
    entered: list[str] = []
    finished: list[str] = []
    releases = {request_id: asyncio.Event() for request_id in request_ids}
    four_started = asyncio.Event()
    six_started = asyncio.Event()
    active = peak = closed = 0

    class FakeCollector:
        def __init__(self, *_args: object) -> None:
            pass

        async def verify(self, request_id: str, requirement: str) -> CollectorVerification:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            entered.append(request_id)
            if len(entered) == 4:
                four_started.set()
            if len(entered) == 6:
                six_started.set()
            try:
                await releases[request_id].wait()
                finished.append(request_id)
                file = CollectorFile(request_id, f"{request_id}.txt", "text/plain", 8, "a" * 64)
                return CollectorVerification(request_id, "file", "verified", [file])
            finally:
                active -= 1

        async def aclose(self) -> None:
            nonlocal closed
            closed += 1

    monkeypatch.setattr(routes, "CollectorClient", FakeCollector)
    listing = asyncio.create_task(routes.collector_verifications("run-1", registry, settings))
    try:
        await asyncio.wait_for(four_started.wait(), timeout=2)
        await asyncio.sleep(0)
        assert len(entered) == 4
        releases[request_ids[3]].set()
        releases[request_ids[2]].set()
        await asyncio.wait_for(six_started.wait(), timeout=2)
        for release in releases.values():
            release.set()
        result = cast(list[dict[str, Any]], await asyncio.wait_for(listing, timeout=2))
    finally:
        for release in releases.values():
            release.set()
        if not listing.done():
            listing.cancel()
        await asyncio.gather(listing, return_exceptions=True)

    assert peak == 4
    assert closed == 6
    assert finished[0] == request_ids[3]
    assert [row["scenarioId"] for row in result] == [f"case-{index}" for index in range(6)]
    assert [row["files"][0]["fileId"] for row in result] == request_ids
    cached = await routes.collector_verifications("run-1", registry, settings)
    assert cached == result
    assert entered == request_ids
    assert {path.name: path.read_bytes() for path in root.glob("*.json")} == original


async def test_preview_recovers_only_files_from_run_scoped_exact_requests(
    collector_run: tuple[Settings, InMemoryRegistry, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, registry, root = collector_run
    request_id = "c" * 32
    _manifest(
        root,
        "recoverable",
        [
            {"request_id": "not-an-exact-id", "requirement": "file", "files": []},
            {"request_id": request_id, "requirement": "file", "status": "failed", "files": []},
        ],
    )
    verified: list[str] = []

    class FakeCollector:
        def __init__(self, *_args: object) -> None:
            pass

        async def verify(self, exact_id: str, requirement: str) -> CollectorVerification:
            assert exact_id == request_id
            verified.append(exact_id)
            file = CollectorFile("recovered", "evidence.txt", "text/plain", 8, "a" * 64)
            return CollectorVerification(exact_id, "file", "verified", [file])

        async def download(self, file: CollectorFile) -> bytes:
            assert file.file_id == "recovered"
            return b"evidence"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(routes, "CollectorClient", FakeCollector)
    with pytest.raises(HTTPException) as unknown:
        await routes.collector_file_preview("run-1", "unknown", registry, settings)
    assert unknown.value.status_code == 404
    response = await routes.collector_file_preview("run-1", "recovered", registry, settings)
    assert response.body == b"evidence"
    with pytest.raises(HTTPException) as unowned:
        await routes.collector_file_preview("run-2", "recovered", registry, settings)
    assert unowned.value.status_code == 404
    assert verified == [request_id]
