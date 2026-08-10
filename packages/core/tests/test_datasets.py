import pytest
from gamr_core.datasets import (
    DatasetManifest,
    DiscoveryPlan,
    Scenario,
    render_template,
    validate_template_placeholders,
)


def test_dataset_manifest_accepts_fixture_shape() -> None:
    manifest = DatasetManifest.model_validate(
        {
            "schemaVersion": "1.0",
            "kind": "dataset",
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "cases": ["case.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
            },
        }
    )
    assert manifest.metadata.id == "demo"


def test_migration_manifest_preserves_selection_and_variables() -> None:
    manifest = DatasetManifest.model_validate(
        {
            "metadata": {"id": "first-plan", "title": "First Plan", "version": "2.0.0"},
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
    assert manifest.spec.defaults.default_case_ids == [
        "visualize-file-as-image-fresh-agent-upload"
    ]
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
    with pytest.raises(ValueError, match="unknown dataset template variables"):
        validate_template_placeholders("Use {typo}.", {"path"})
