import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image
from scripts.render_judge_graph import render_judge_graph


def test_render_judge_graph_valid_directory(tmp_path: Path) -> None:
    judge_dir = Path("packages/engine/src/gamr_engine/judges/evidence_and_content")
    out_dir = tmp_path / "docs" / "assets" / "judges"
    out_dir.mkdir(parents=True)
    target = out_dir / "evidence-and-content.png"

    result_path = render_judge_graph(judge_dir, destination=target)
    assert result_path.exists()
    assert result_path == target

    # Check PNG signature and non-zero dimensions
    with Image.open(result_path) as img:
        assert img.format == "PNG"
        assert img.width > 0
        assert img.height > 0


def test_render_judge_graph_includes_expected_nodes(tmp_path: Path) -> None:
    from gamr_engine.judges.registry import get_judge_pipeline

    judge_dir = Path("packages/engine/src/gamr_engine/judges/evidence_and_content")
    out_dir = tmp_path / "docs" / "assets" / "judges"
    out_dir.mkdir(parents=True)
    target = out_dir / "evidence-and-content.png"

    result_path = render_judge_graph(judge_dir, destination=target)
    assert result_path.exists()

    pipeline = get_judge_pipeline("evidence-and-content")
    nodes = set(pipeline.graph.get_graph().nodes.keys())
    expected_nodes = {
        "prepare_verified_content",
        "decode_trajectory_content",
        "compare_reference_content",
        "assess_evidence",
        "finalize_judgment",
    }
    assert expected_nodes.issubset(nodes)


def test_render_judge_graph_repeated_output_and_atomic_replacement(tmp_path: Path) -> None:
    judge_dir = Path("packages/engine/src/gamr_engine/judges/evidence_and_content")
    out_dir = tmp_path / "docs" / "assets" / "judges"
    out_dir.mkdir(parents=True)
    target = out_dir / "evidence-and-content.png"

    # First render
    render_judge_graph(judge_dir, destination=target)
    assert target.exists()

    # Second render
    render_judge_graph(judge_dir, destination=target)
    assert target.exists()

    with Image.open(target) as img:
        assert img.format == "PNG"


@pytest.mark.parametrize(
    "invalid_path",
    [
        "packages/engine/src/gamr_engine/judges/nonexistent",
        "packages/engine/src/gamr_engine/judges/contracts.py",
        "packages/engine/src/gamr_engine",
        "../outside",
        "packages/engine/src/gamr_engine/judges/../../..",
    ],
)
def test_render_judge_graph_invalid_paths_fail_closed(invalid_path: str, tmp_path: Path) -> None:
    out_dir = tmp_path / "docs" / "assets" / "judges"
    out_dir.mkdir(parents=True)
    target = out_dir / "test.png"

    with pytest.raises((ValueError, FileNotFoundError)):
        render_judge_graph(Path(invalid_path), destination=target)


def test_render_preserves_existing_target_on_failure(tmp_path: Path) -> None:
    out_dir = tmp_path / "docs" / "assets" / "judges"
    out_dir.mkdir(parents=True)
    target = out_dir / "evidence-and-content.png"
    target.write_bytes(b"existing-png-content")

    # Invalid render should fail and not overwrite existing file
    with pytest.raises(ValueError):
        render_judge_graph(Path("packages/engine/src/gamr_engine"), destination=target)

    assert target.read_bytes() == b"existing-png-content"
