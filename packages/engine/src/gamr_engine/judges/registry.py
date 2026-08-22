from __future__ import annotations

from gamr_core import JudgePipelineId

from .contracts import JudgePipeline
from .evidence_and_content.pipeline import EvidenceAndContentPipeline

_REGISTRY: dict[str, JudgePipeline] = {
    "evidence-and-content": EvidenceAndContentPipeline(),
}


def get_judge_pipeline(pipeline_id: JudgePipelineId | str) -> JudgePipeline:
    if pipeline_id not in _REGISTRY:
        raise KeyError(f"unknown judge pipeline: {pipeline_id!r}")
    return _REGISTRY[pipeline_id]
