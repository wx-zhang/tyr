from __future__ import annotations

from typing import Any

from gamr_engine.content_evidence import ContentEvidenceProvider
from gamr_engine.content_source import VerifiedContentSource
from gamr_engine.judges.contracts import JudgeRuntime
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.ports.models import ModelGateway
from gamr_engine.ports.sandbox import Sandbox


def build_judge_runtime(
    *,
    judge_model: ModelGateway,
    content_evidence_provider: ContentEvidenceProvider | None,
    verified_content_source: VerifiedContentSource | None = None,
    sandbox: Sandbox | None = None,
    artifacts: ArtifactStore | None,
    activity_sink: Any | None,
    run_id: str,
    case_id: str,
) -> JudgeRuntime:
    source = verified_content_source
    if source is None and content_evidence_provider is not None:
        if callable(getattr(content_evidence_provider, "fetch_verified_snapshot", None)):
            source = content_evidence_provider  # type: ignore[assignment]
    return JudgeRuntime(
        judge_model=judge_model,
        content_evidence_provider=content_evidence_provider,
        verified_content_source=source,
        sandbox=sandbox,
        artifacts=artifacts,
        activity_sink=activity_sink,
        run_id=run_id,
        case_id=case_id,
    )
