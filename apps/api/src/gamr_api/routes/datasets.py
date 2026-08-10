from pathlib import Path

from fastapi import APIRouter, Depends
from gamr_adapters.config import Settings
from gamr_adapters.datasets.filesystem import (
    FilesystemDatasetRepository,
    load_dataset,
    resolve_dataset_directory,
)

from ..dependencies import get_settings
from ..errors import not_found

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("")
def list_datasets(settings: Settings = Depends(get_settings)) -> list[dict[str, object]]:
    return [
        manifest.model_dump(by_alias=True)
        for manifest in FilesystemDatasetRepository(settings.dataset_root).list()
    ]


@router.post("/validate")
def validate_dataset(
    payload: dict[str, str], settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    directory = Path(payload.get("directory", settings.dataset_root))
    try:
        manifest, scenarios = FilesystemDatasetRepository(settings.dataset_root).load(directory)
    except Exception as error:
        return {"valid": False, "errors": [str(error)]}
    return {"valid": True, "datasetId": manifest.metadata.id, "caseCount": len(scenarios)}


@router.get("/{dataset_id}/cases")
def list_dataset_cases(
    dataset_id: str, settings: Settings = Depends(get_settings)
) -> list[dict[str, object]]:
    try:
        directory = resolve_dataset_directory(settings.dataset_root, dataset_id)
        _, scenarios = FilesystemDatasetRepository(settings.dataset_root).load(directory)
    except ValueError as error:
        raise not_found("dataset") from error
    return [
        scenario.model_dump(by_alias=True, exclude_none=True) for scenario in scenarios
    ]


@router.get("/{dataset_id}/plans")
def get_dataset_plans(
    dataset_id: str, settings: Settings = Depends(get_settings)
) -> dict[str, object | None]:
    try:
        directory = resolve_dataset_directory(settings.dataset_root, dataset_id)
        loaded = load_dataset(directory)
    except ValueError as error:
        raise not_found("dataset") from error
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
    }


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    for manifest in FilesystemDatasetRepository(settings.dataset_root).list():
        if manifest.metadata.id == dataset_id:
            return manifest.model_dump(by_alias=True)
    raise not_found("dataset")
