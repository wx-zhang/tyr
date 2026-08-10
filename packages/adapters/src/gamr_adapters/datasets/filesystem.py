from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from gamr_core.datasets import (
    DatasetManifest,
    DiscoveryPlan,
    EvaluationPlan,
    PromptBundle,
    Scenario,
    parse_json_file,
    validate_template_placeholders,
)
from gamr_engine.runner import LoadedDataset


def resolve_dataset_directory(root: str | Path, reference: str | Path) -> Path:
    root_path = Path(root).resolve()
    ref = Path(reference)
    if ref.is_absolute():
        candidate = ref.resolve()
    else:
        parts = ref.parts
        if parts and parts[0] == root_path.name:
            ref = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        candidate = (root_path / ref).resolve()
    if root_path != candidate and root_path not in candidate.parents:
        raise ValueError("dataset reference escapes dataset root")
    if not candidate.is_dir():
        raise ValueError(f"dataset directory does not exist: {candidate}")
    return candidate


class FilesystemDatasetRepository:
    def __init__(self, root: str | Path = "datasets") -> None:
        self.root = Path(root)

    def _dataset_directory(self, reference: str | Path) -> Path:
        return resolve_dataset_directory(self.root, reference)

    @staticmethod
    def _file(directory: Path, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            raise ValueError(f"dataset reference must be relative: {relative_path}")
        resolved = (directory / path).resolve()
        if directory not in resolved.parents or not resolved.is_file():
            raise ValueError(f"dataset reference escapes or does not exist: {relative_path}")
        return resolved

    def list(self) -> Sequence[DatasetManifest]:
        manifests: list[DatasetManifest] = []
        for path in sorted(self.root.glob("*/dataset.json")):
            manifests.append(DatasetManifest.model_validate(parse_json_file(path)))
        return manifests

    def load(self, reference: str | Path) -> tuple[DatasetManifest, Sequence[Scenario]]:
        directory = self._dataset_directory(reference)
        manifest = DatasetManifest.model_validate(
            parse_json_file(self._file(directory, "dataset.json"))
        )
        scenarios = [
            Scenario.model_validate(parse_json_file(self._file(directory, case_path)))
            for case_path in manifest.spec.cases
        ]
        scenario_ids = [scenario.metadata.id for scenario in scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("dataset scenario IDs must be unique")
        missing_defaults = set(manifest.spec.defaults.default_case_ids) - set(scenario_ids)
        if missing_defaults:
            raise ValueError(f"default case IDs are not in the dataset: {sorted(missing_defaults)}")
        declared = set(manifest.spec.variables)
        for scenario in scenarios:
            texts = [scenario.metadata.title, scenario.spec.objective, *scenario.spec.steps]
            if scenario.spec.success_criteria:
                texts.append(scenario.spec.success_criteria)
            for text in texts:
                validate_template_placeholders(text, declared)
        return manifest, scenarios


def load_dataset(directory: str | Path) -> LoadedDataset:
    repository = FilesystemDatasetRepository()
    dataset_directory = repository._dataset_directory(directory)
    manifest, scenarios = repository.load(dataset_directory)

    discovery = None
    if manifest.spec.discovery:
        discovery = DiscoveryPlan.model_validate(
            parse_json_file(repository._file(dataset_directory, manifest.spec.discovery))
        )
    methodology = None
    if manifest.spec.methodology:
        methodology = PromptBundle.model_validate(
            parse_json_file(repository._file(dataset_directory, manifest.spec.methodology))
        )
    evaluation = None
    if manifest.spec.evaluation:
        evaluation = EvaluationPlan.model_validate(
            parse_json_file(repository._file(dataset_directory, manifest.spec.evaluation))
        )

    raw = {
        "manifest": manifest.model_dump(by_alias=True, exclude_none=True),
        "discovery": discovery.model_dump(by_alias=True, exclude_none=True) if discovery else None,
        "methodology": methodology.model_dump(by_alias=True, exclude_none=True)
        if methodology
        else None,
        "evaluation": (
            evaluation.model_dump(by_alias=True, exclude_none=True) if evaluation else None
        ),
        "scenarios": [
            scenario.model_dump(by_alias=True, exclude_none=True) for scenario in scenarios
        ],
    }
    return LoadedDataset(
        manifest=manifest,
        scenarios=list(scenarios),
        raw=raw,
        discovery=discovery,
        methodology=methodology,
        evaluation=evaluation,
    )
