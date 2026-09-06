from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from gamr_core.tasks import (
    DiscoveryPlan,
    EvaluationPlan,
    PromptBundle,
    Scenario,
    TaskManifest,
    parse_json_file,
    validate_template_placeholders,
)
from gamr_engine.content_evidence import AssessmentReference
from gamr_engine.experiments.records import LoadedTask

MAX_ASSESSMENT_REFERENCE_BYTES = 256 * 1024


def resolve_task_directory(root: str | Path, reference: str | Path) -> Path:
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
        raise ValueError("task reference escapes task root")
    if not candidate.is_dir():
        raise ValueError(f"task directory does not exist: {candidate}")
    return candidate


class FilesystemTaskRepository:
    def __init__(self, root: str | Path = "tasks") -> None:
        self.root = Path(root)

    def _task_directory(self, reference: str | Path) -> Path:
        return resolve_task_directory(self.root, reference)

    @staticmethod
    def _file(directory: Path, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            raise ValueError(f"task reference must be relative: {relative_path}")
        resolved = (directory / path).resolve()
        if directory not in resolved.parents or not resolved.is_file():
            raise ValueError(f"task reference escapes or does not exist: {relative_path}")
        return resolved

    def list(self) -> Sequence[TaskManifest]:
        manifests: list[TaskManifest] = []
        for path in sorted(self.root.glob("*/task.json")):
            manifests.append(TaskManifest.model_validate(parse_json_file(path)))
        return manifests

    def load(self, reference: str | Path) -> tuple[TaskManifest, Sequence[Scenario]]:
        directory = self._task_directory(reference)
        manifest = TaskManifest.model_validate(parse_json_file(self._file(directory, "task.json")))
        scenarios = [
            Scenario.model_validate(parse_json_file(self._file(directory, scenario_path)))
            for scenario_path in manifest.spec.scenarios
        ]
        scenario_ids = [scenario.metadata.id for scenario in scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("task scenario IDs must be unique")
        missing_defaults = set(manifest.spec.defaults.default_scenario_ids) - set(scenario_ids)
        if missing_defaults:
            raise ValueError(
                f"default scenario IDs are not in the task: {sorted(missing_defaults)}"
            )
        declared = set(manifest.spec.variables)
        for scenario in scenarios:
            texts = [scenario.metadata.title, scenario.spec.objective, *scenario.spec.steps]
            if scenario.spec.success_criteria:
                texts.append(scenario.spec.success_criteria)
            for text in texts:
                validate_template_placeholders(text, declared)
        return manifest, scenarios


def load_task(directory: str | Path) -> LoadedTask:
    repository = FilesystemTaskRepository()
    task_directory = repository._task_directory(directory)
    manifest, scenarios = repository.load(task_directory)

    discovery = None
    if manifest.spec.discovery:
        discovery = DiscoveryPlan.model_validate(
            parse_json_file(repository._file(task_directory, manifest.spec.discovery))
        )
    methodology = None
    if manifest.spec.methodology:
        methodology = PromptBundle.model_validate(
            parse_json_file(repository._file(task_directory, manifest.spec.methodology))
        )
    evaluation = None
    if manifest.spec.evaluation:
        evaluation = EvaluationPlan.model_validate(
            parse_json_file(repository._file(task_directory, manifest.spec.evaluation))
        )

    assessment_reference = None
    reference_metadata = None
    if evaluation is not None and evaluation.reference is not None:
        try:
            reference_path = repository._file(task_directory, evaluation.reference.file)
        except ValueError as error:
            raise ValueError(f"invalid evaluation reference: {error}") from error
        content_bytes = reference_path.read_bytes()
        if not content_bytes or len(content_bytes) > MAX_ASSESSMENT_REFERENCE_BYTES:
            raise ValueError("evaluation reference must contain 1 to 262144 bytes")
        try:
            content = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("evaluation reference must be UTF-8 text") from error
        if not content.strip() or "\x00" in content:
            raise ValueError("evaluation reference must be non-empty text without NUL bytes")
        digest = hashlib.sha256(content_bytes).hexdigest()
        assessment_reference = AssessmentReference(
            reference_path.name,
            content,
            digest,
            len(content_bytes),
        )
        reference_metadata = {
            "file": evaluation.reference.file,
            "classification": evaluation.reference.classification,
            "size": len(content_bytes),
            "sha256": f"sha256:{digest}",
        }

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
    if reference_metadata is not None:
        raw["assessmentReference"] = reference_metadata
    return LoadedTask(
        manifest=manifest,
        scenarios=list(scenarios),
        raw=raw,
        discovery=discovery,
        methodology=methodology,
        evaluation=evaluation,
        assessment_reference=assessment_reference,
    )
