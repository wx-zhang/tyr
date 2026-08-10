from pathlib import Path

from gamr_adapters.datasets.filesystem import load_dataset


def test_fixture_dataset_loads() -> None:
    dataset = load_dataset(Path("datasets/first-plan"))
    assert dataset.manifest.metadata.id == "first-plan"
    assert dataset.manifest.metadata.version == "2.0.0"
    assert [scenario.metadata.id for scenario in dataset.scenarios] == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload",
        "archive-compress-fresh-agent-upload",
        "reformat-to-json-fresh-agent-upload",
        "two-agent-relay-upload",
    ]
    assert dataset.manifest.spec.defaults.default_case_ids == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload"
    ]
    assert [len(scenario.spec.steps) for scenario in dataset.scenarios] == [15, 17, 18, 14, 17]
    assert all(scenario.spec.success_criteria for scenario in dataset.scenarios)
    assert dataset.discovery is not None
    assert dataset.methodology is not None
    assert dataset.evaluation is not None
