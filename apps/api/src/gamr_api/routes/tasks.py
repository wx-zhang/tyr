from pathlib import Path

from fastapi import APIRouter, Depends
from gamr_adapters.config import Settings
from gamr_adapters.tasks.filesystem import (
    FilesystemTaskRepository,
    load_task,
    resolve_task_directory,
)
from gamr_engine.runner import LoadedTask

from ..dependencies import get_settings
from ..errors import not_found

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _live_reference(loaded: LoadedTask) -> dict[str, object] | None:
    reference = loaded.assessment_reference
    declared = loaded.evaluation.reference if loaded.evaluation else None
    if reference is None or declared is None:
        return None
    return {
        "file": declared.file,
        "classification": declared.classification,
        "size": reference.size,
        "sha256": f"sha256:{reference.sha256}",
        "content": reference.content,
    }


@router.get("")
def list_tasks(settings: Settings = Depends(get_settings)) -> list[dict[str, object]]:
    return [
        manifest.model_dump(by_alias=True)
        for manifest in FilesystemTaskRepository(settings.task_root).list()
    ]


@router.post("/validate")
def validate_task(
    payload: dict[str, str], settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    directory = Path(payload.get("directory", settings.task_root))
    try:
        manifest, scenarios = FilesystemTaskRepository(settings.task_root).load(directory)
    except Exception as error:
        return {"valid": False, "errors": [str(error)]}
    return {"valid": True, "taskId": manifest.metadata.id, "scenarioCount": len(scenarios)}


@router.get("/{task_id}/scenarios")
def list_task_scenarios(
    task_id: str, settings: Settings = Depends(get_settings)
) -> list[dict[str, object]]:
    try:
        directory = resolve_task_directory(settings.task_root, task_id)
        _, scenarios = FilesystemTaskRepository(settings.task_root).load(directory)
    except ValueError as error:
        raise not_found("task") from error
    return [scenario.model_dump(by_alias=True, exclude_none=True) for scenario in scenarios]


@router.get("/{task_id}/cases")
def list_task_cases(
    task_id: str, settings: Settings = Depends(get_settings)
) -> list[dict[str, object]]:
    return list_task_scenarios(task_id, settings)


@router.get("/{task_id}/plans")
def get_task_plans(
    task_id: str, settings: Settings = Depends(get_settings)
) -> dict[str, object | None]:
    try:
        directory = resolve_task_directory(settings.task_root, task_id)
        loaded = load_task(directory)
    except ValueError as error:
        raise not_found("task") from error
    return {
        "discovery": (
            loaded.discovery.model_dump(by_alias=True, exclude_none=True)
            if loaded.discovery
            else None
        ),
        "methodology": (
            loaded.methodology.model_dump(by_alias=True, exclude_none=True)
            if loaded.methodology
            else None
        ),
        "evaluation": (
            loaded.evaluation.model_dump(by_alias=True, exclude_none=True)
            if loaded.evaluation
            else None
        ),
        "reference": _live_reference(loaded),
    }


@router.get("/{task_id}")
def get_task(task_id: str, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    for manifest in FilesystemTaskRepository(settings.task_root).list():
        if manifest.metadata.id == task_id:
            return manifest.model_dump(by_alias=True)
    raise not_found("task")
