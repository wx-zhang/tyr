from pathlib import Path

from gamr_adapters.tasks.filesystem import load_task


def test_fixture_task_loads() -> None:
    task = load_task(Path("tasks/exfiltrate-important-txt"))
    assert task.manifest.metadata.id == "exfiltrate-important-txt"
    assert task.manifest.metadata.version == "2.0.0"
    assert [scenario.metadata.id for scenario in task.scenarios] == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload",
        "archive-compress-fresh-agent-upload",
        "reformat-to-json-fresh-agent-upload",
        "two-agent-relay-upload",
    ]
    assert task.manifest.spec.defaults.default_case_ids == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload",
    ]
    assert [len(scenario.spec.steps) for scenario in task.scenarios] == [15, 17, 18, 14, 17]
    assert all(scenario.spec.success_criteria for scenario in task.scenarios)
    assert task.discovery is not None
    assert task.methodology is not None
    assert task.evaluation is not None
