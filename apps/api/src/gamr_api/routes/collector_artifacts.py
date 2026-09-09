from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from gamr_adapters.collector import CollectorClient, CollectorError
from gamr_adapters.config import Settings
from gamr_engine.collector_verification import CollectorFile, CollectorRequirement
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..dependencies import get_registry, get_settings, require_run_evidence_access
from ..errors import not_found
from ..registry import InMemoryRegistry

router = APIRouter(prefix="/api/v1/runs", tags=["collector-artifacts"])
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_PREVIEW_BYTES = 5 * 1024 * 1024
_IMAGE_PREVIEW_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}
_TEXT_PREVIEW_TYPES = {
    "application/json",
    "application/xml",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/xml",
}
_REMOTE_FILES_CACHE: dict[tuple[str, str, str], list[CollectorFile]] = {}


class CollectorFileResponse(BaseModel):
    file_id: str = Field(alias="fileId")
    filename: str
    content_type: str = Field(alias="contentType")
    size: int
    sha256: str
    download_available: bool = Field(alias="downloadAvailable")

    model_config = ConfigDict(populate_by_name=True)


class CollectorVerificationResponse(BaseModel):
    scenario_id: str | None = Field(default=None, alias="scenarioId")
    scenario_execution_id: str | None = Field(
        default=None,
        alias="scenarioExecutionId",
        validation_alias=AliasChoices("scenarioExecutionId", "caseId"),
    )
    requirement: str
    status: str
    request_ids: list[str] = Field(alias="requestIds")
    files: list[CollectorFileResponse]
    verified_at: str | None = Field(default=None, alias="verifiedAt")

    model_config = ConfigDict(populate_by_name=True)


def _manifests(run_id: str, settings: Settings) -> list[dict[str, Any]]:
    artifact_root = Path(settings.artifact_root).resolve()
    root = (artifact_root / "runs" / run_id / "collector-verifications").resolve()
    if artifact_root not in root.parents or not root.is_dir():
        return []
    values: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _files(manifest: dict[str, Any]) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for request in manifest.get("requests", []):
        if not isinstance(request, dict):
            continue
        for file in request.get("files", []):
            if not isinstance(file, dict):
                continue
            files.append(
                {
                    "fileId": file.get("file_id"),
                    "filename": file.get("filename"),
                    "contentType": file.get("content_type"),
                    "size": file.get("size"),
                    "sha256": file.get("sha256"),
                    "downloadAvailable": request.get("status") == "verified",
                }
            )
    return files


@router.get(
    "/{run_id}/collector-verifications",
    response_model=list[CollectorVerificationResponse],
)
async def collector_verifications(
    run_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    require_run_evidence_access(run_id, registry)
    results: list[dict[str, object]] = []
    manifests = _manifests(run_id, settings)
    semaphore = asyncio.Semaphore(4)

    async def hydrate(value: dict[str, Any]) -> list[dict[str, object]]:
        async with semaphore:
            return await _remote_files(value, settings)

    remote_files = await asyncio.gather(*(hydrate(value) for value in manifests))
    for value, recovered in zip(manifests, remote_files, strict=True):
        files = _files(value)
        files.extend(recovered)
        results.append(
            {
                "scenarioId": value.get("scenarioId", value.get("caseId")),
                "scenarioExecutionId": value.get(
                    "scenarioExecutionId", value.get("caseId")
                ),
                "requirement": value.get("requirement"),
                "status": value.get("status"),
                "requestIds": [
                    item.get("request_id")
                    for item in value.get("requests", [])
                    if isinstance(item, dict) and item.get("request_id")
                ],
                "files": files,
                "verifiedAt": value.get("verifiedAt"),
            }
        )
    return results


async def _find_file(run_id: str, file_id: str, settings: Settings) -> CollectorFile:
    manifests = _manifests(run_id, settings)
    for recover_remote in (False, True):
        for manifest in manifests:
            items = await _remote_files(manifest, settings) if recover_remote else _files(manifest)
            for item in items:
                if item.get("fileId") == file_id and item.get("downloadAvailable"):
                    size = item.get("size")
                    if not isinstance(size, int):
                        continue
                    return CollectorFile(
                        str(item["fileId"]),
                        str(item["filename"]),
                        str(item["contentType"]),
                        size,
                        str(item["sha256"]),
                    )
    raise not_found("collector file")


async def _remote_files(manifest: dict[str, Any], settings: Settings) -> list[dict[str, object]]:
    existing_ids = {item.get("fileId") for item in _files(manifest)}
    requests: list[tuple[str, CollectorRequirement]] = []
    for item in manifest.get("requests", []):
        if not isinstance(item, dict) or item.get("files"):
            continue
        request_id = item.get("request_id")
        requirement = item.get("requirement") or manifest.get("requirement")
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
            continue
        if requirement not in {"request", "file"}:
            continue
        requests.append((request_id, cast(CollectorRequirement, requirement)))
    files: list[dict[str, object]] = []
    for request_id, requirement in requests:
        for file in await _verified_remote_files(request_id, requirement, settings):
            if file.file_id not in existing_ids:
                files.append(_file_response(file))
                existing_ids.add(file.file_id)
    return files


async def _verified_remote_files(
    request_id: str, requirement: CollectorRequirement, settings: Settings
) -> list[CollectorFile]:
    cache_key = (settings.collector_base_url, request_id, requirement)
    if cache_key in _REMOTE_FILES_CACHE:
        return _REMOTE_FILES_CACHE[cache_key]
    if not settings.collector_username or not settings.collector_password:
        return []
    client = CollectorClient(
        settings.collector_base_url,
        settings.collector_username,
        settings.collector_password,
    )
    try:
        try:
            verified = await client.verify(request_id, requirement)
        except CollectorError, httpx.HTTPError, OSError:
            return []
    finally:
        await client.aclose()
    _REMOTE_FILES_CACHE[cache_key] = verified.files
    return verified.files


def _file_response(file: CollectorFile) -> dict[str, object]:
    return {
        "fileId": file.file_id,
        "filename": file.filename,
        "contentType": file.content_type,
        "size": file.size,
        "sha256": file.sha256,
        "downloadAvailable": True,
    }


async def _download_file(file: CollectorFile, settings: Settings) -> bytes:
    if not settings.collector_username or not settings.collector_password:
        raise HTTPException(status_code=503, detail="Collector credentials are unavailable")
    client = CollectorClient(
        settings.collector_base_url,
        settings.collector_username,
        settings.collector_password,
    )
    try:
        try:
            return await client.download(file)
        except (CollectorError, httpx.HTTPError, OSError) as error:
            raise HTTPException(
                status_code=502, detail="Collector artifact could not be verified"
            ) from error
    finally:
        await client.aclose()


def _preview_media_type(file: CollectorFile) -> str | None:
    content_type = file.content_type.split(";", 1)[0].strip().lower()
    if content_type in _IMAGE_PREVIEW_TYPES:
        return content_type
    if content_type in _TEXT_PREVIEW_TYPES:
        return "text/plain"
    if content_type == "application/octet-stream" and Path(file.filename).suffix.lower() in {
        ".md",
        ".markdown",
        ".txt",
    }:
        return "text/plain"
    return None


@router.get("/{run_id}/collector-files/{file_id}/preview")
async def collector_file_preview(
    run_id: str,
    file_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_run_evidence_access(run_id, registry)
    file = await _find_file(run_id, file_id, settings)
    media_type = _preview_media_type(file)
    if media_type is None:
        raise HTTPException(status_code=415, detail="Collector artifact preview is unsupported")
    if file.size > _MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="Collector artifact preview is too large")
    content = await _download_file(file, settings)
    filename = _SAFE_FILENAME.sub("-", Path(file.filename).name)[:180] or "artifact"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{run_id}/collector-files/{file_id}/download")
async def collector_file_download(
    run_id: str,
    file_id: str,
    registry: InMemoryRegistry = Depends(get_registry),
    settings: Settings = Depends(get_settings),
) -> Response:
    require_run_evidence_access(run_id, registry)
    file = await _find_file(run_id, file_id, settings)
    content = await _download_file(file, settings)
    filename = _SAFE_FILENAME.sub("-", Path(file.filename).name)[:180] or "artifact"
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
