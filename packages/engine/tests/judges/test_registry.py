import pytest
from gamr_engine.judges.registry import get_judge_pipeline


def test_registry_resolves_evidence_and_content() -> None:
    assert get_judge_pipeline is not None
    pipeline = get_judge_pipeline("evidence-and-content")
    assert pipeline.id == "evidence-and-content"
    assert pipeline.graph is not None
    assert callable(pipeline.run)


def test_registry_rejects_unknown_pipeline() -> None:
    assert get_judge_pipeline is not None
    with pytest.raises(KeyError, match="unknown judge pipeline"):
        get_judge_pipeline("unknown-pipeline")


@pytest.mark.parametrize(
    "unsafe_identifier",
    [
        "gamr_engine.judges.evidence_and_content:pipeline",
        "os.system",
        "../custom_pipeline",
        "https://example.com/judge.py",
        "evidence_and_content.pipeline",
    ],
)
def test_registry_never_imports_or_looks_up_filesystem(unsafe_identifier: str) -> None:
    assert get_judge_pipeline is not None
    with pytest.raises(KeyError):
        get_judge_pipeline(unsafe_identifier)
