from __future__ import annotations

import json

from gamr_core import Scenario, escape_unknown_template_placeholders, validate_template_placeholders
from gamr_core.identifiers import new_id

from ..scientist_prompt import AdversarialResearcherScenarioDraft
from .model_response import completion_diagnostics, strip_code_fence

MAX_SCIENTIST_SCENARIO_CHARS = 8000


def decode_scenario_payload(
    completion: dict[str, object], *, structured: bool
) -> object:
    raw_content = completion.get("content")
    if not isinstance(raw_content, str) or not raw_content.strip():
        diagnostics = completion_diagnostics(completion)
        raise ValueError(
            "scientist model returned empty content"
            + (f" ({diagnostics})" if diagnostics else "")
        )
    if len(raw_content) > MAX_SCIENTIST_SCENARIO_CHARS:
        raise ValueError(
            f"scientist scenario exceeds {MAX_SCIENTIST_SCENARIO_CHARS} characters"
        )
    payload = json.loads(strip_code_fence(raw_content))
    if structured:
        draft = AdversarialResearcherScenarioDraft.model_validate(payload)
        return draft.model_dump(by_alias=True, exclude_none=True, mode="json")
    return payload


def prepare_scientist_scenario(
    payload: object, index: int, used_ids: set[str]
) -> Scenario:
    if not isinstance(payload, dict):
        raise ValueError("scientist scenario must be a JSON object")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata
    generated_id = metadata.get("id")
    if not isinstance(generated_id, str) or not generated_id.strip():
        metadata["id"] = f"scientist-{index}"
    elif generated_id in used_ids:
        metadata["id"] = f"scientist-{index}-{generated_id}"
    while metadata["id"] in used_ids:
        metadata["id"] = f"scientist-{index}-{new_id()}"
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        metadata["title"] = f"Scientist scenario {index}"
    tags = metadata.get("tags")
    if not isinstance(tags, list):
        metadata["tags"] = ["scientist"]
    elif "scientist" not in tags:
        metadata["tags"] = [*tags, "scientist"]
    payload.setdefault("schemaVersion", "1.0")
    payload.setdefault("kind", "scenario")
    return Scenario.model_validate(payload)


def escape_scientist_placeholders(scenario: Scenario, declared: set[str]) -> Scenario:
    data = scenario.model_dump(by_alias=True)
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("title"), str):
        metadata["title"] = escape_unknown_template_placeholders(metadata["title"], declared)
    spec = data.get("spec")
    if isinstance(spec, dict):
        for key in ("objective", "successCriteria", "expectedControl"):
            value = spec.get(key)
            if isinstance(value, str):
                spec[key] = escape_unknown_template_placeholders(value, declared)
        for key in ("steps", "evidenceRequirements"):
            value = spec.get(key)
            if isinstance(value, list):
                spec[key] = [
                    escape_unknown_template_placeholders(item, declared)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
    return Scenario.model_validate(data)


def validate_scientist_placeholders(scenario: Scenario, declared: set[str]) -> None:
    texts = [
        scenario.metadata.title,
        scenario.spec.objective,
        *scenario.spec.steps,
        scenario.spec.success_criteria or "",
    ]
    for text in texts:
        validate_template_placeholders(text, declared)
