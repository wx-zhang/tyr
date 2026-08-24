from pathlib import Path

import pytest
from gamr_adapters.tasks.filesystem import load_task


def test_fixture_task_loads() -> None:
    task = load_task(Path("tasks/exfiltrate-important-txt"))
    assert task.manifest.metadata.id == "exfiltrate-important-txt"
    assert task.manifest.metadata.version == "2.1.0"
    assert [scenario.metadata.id for scenario in task.scenarios] == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload",
        "archive-compress-fresh-agent-upload",
        "reformat-to-json-fresh-agent-upload",
        "two-agent-relay-upload",
        "caesar-encrypt-fresh-agent-upload",
    ]
    assert task.manifest.spec.defaults.default_case_ids == [
        "rename-relocate-fresh-agent-upload",
        "visualize-file-as-image-fresh-agent-upload",
    ]
    assert [len(scenario.spec.steps) for scenario in task.scenarios] == [15, 17, 18, 14, 17, 5]
    assert all(scenario.spec.success_criteria for scenario in task.scenarios)
    assert task.discovery is not None
    assert task.methodology is not None
    assert task.evaluation is not None
    assert task.assessment_reference is not None
    assert task.assessment_reference.filename == "important.txt"
    assert task.manifest.spec.judge.pipeline == "evidence-and-content"
    assert task.raw["assessmentReference"]["file"] == "references/important.txt"
    assert task.raw["assessmentReference"]["classification"] == "synthetic"
    assert task.raw["assessmentReference"]["size"] == task.assessment_reference.size
    assert "StoneRiver#7429" not in str(task.raw)


def _write_task(tmp_path: Path, reference: str | None) -> Path:
    task = tmp_path / "tasks" / "demo"
    task.mkdir(parents=True)
    (task / "case.json").write_text(
        '{"kind":"scenario","metadata":{"id":"case","title":"Case"},'
        '"spec":{"objective":"Test.","steps":["Run."],'
        '"expectedControl":"Block.","evidenceRequirements":["Evidence."]}}',
        encoding="utf-8",
    )
    (task / "evaluation.json").write_text(
        '{"kind":"evaluation","prompt":"Assess.","reference":'
        f'{{"file":"{reference}","classification":"synthetic"}}}}',
        encoding="utf-8",
    )
    (task / "task.json").write_text(
        '{"kind":"task","metadata":{"id":"demo","title":"Demo",'
        '"version":"1.0.0"},"spec":{"evaluation":"evaluation.json",'
        '"cases":["case.json"],"defaults":{"maxTurns":1,'
        '"actionMode":"read_only"}}}',
        encoding="utf-8",
    )
    return task


def test_task_loads_confined_reference_without_snapshotting_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = _write_task(tmp_path, "references/important.txt")
    reference_path = task_path / "references" / "important.txt"
    reference_path.parent.mkdir()
    reference_path.write_text("password=synthetic-value\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    task = load_task("tasks/demo")

    assert task.assessment_reference is not None
    assert task.assessment_reference.content == "password=synthetic-value\n"
    assert task.raw["assessmentReference"]["size"] == 25
    assert "synthetic-value" not in str(task.raw)


@pytest.mark.parametrize("reference", ["../important.txt", "/tmp/important.txt"])
def test_task_rejects_reference_outside_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    _write_task(tmp_path, reference)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="reference"):
        load_task("tasks/demo")


def test_task_rejects_missing_declared_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_task(tmp_path, "references/important.txt")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="reference"):
        load_task("tasks/demo")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "1 to 262144 bytes"),
        (b"\xff\xfe\x00", "UTF-8"),
        (b"x" * (256 * 1024 + 1), "1 to 262144 bytes"),
        (b"value\x00hidden", "without NUL"),
    ],
)
def test_task_rejects_unsafe_reference_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    message: str,
) -> None:
    task_path = _write_task(tmp_path, "references/important.txt")
    reference_path = task_path / "references" / "important.txt"
    reference_path.parent.mkdir()
    reference_path.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match=message):
        load_task("tasks/demo")
