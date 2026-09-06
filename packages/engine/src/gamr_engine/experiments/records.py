from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from gamr_core import (
    CaseResult,
    DiscoveryCandidate,
    DiscoveryPlan,
    EvaluationPlan,
    NextTurnDecision,
    PromptBundle,
    Scenario,
    TargetOrigin,
    TaskManifest,
)

from ..content_evidence import AssessmentReference


@dataclass(frozen=True)
class LoadedTask:
    manifest: TaskManifest
    scenarios: list[Scenario]
    raw: dict[str, Any]
    discovery: DiscoveryPlan | None = None
    methodology: PromptBundle | None = None
    evaluation: EvaluationPlan | None = None
    assessment_reference: AssessmentReference | None = None

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.raw, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class PhaseResult:
    transcript: list[dict[str, str]]
    operation_id: str | None
    decision: NextTurnDecision | None
    candidates: list[DiscoveryCandidate]
    error: str | None = None
    target_origin: TargetOrigin = TargetOrigin.LIVE


@dataclass
class TargetConversation:
    operation_id: str | None = None
    conversation_id: str | None = None
    seen_reply: str = ""


@dataclass(frozen=True)
class ScenarioExecutionRecord:
    scenario: Scenario
    rendered_title: str
    rendered_objective: str
    rendered_steps: list[str]
    rendered_success: str
    case: CaseResult
    transcript: list[dict[str, str]]
    origin: str = "base"
    origin_run_id: str | None = None
    origin_artifact_id: str | None = None
    source_created_at: datetime | None = None
    scenario_execution_id: str | None = None


@dataclass(frozen=True)
class RenderedScenario:
    title: str
    objective: str
    steps: list[str]
    success: str
    expected_control: str


@dataclass(frozen=True)
class ProgressEvent:
    event_type: str
    run_id: str
    phase: str | None = None
    case_id: str | None = None
    scenario_id: str | None = None
    scenario_execution_id: str | None = None
    turn: int | None = None
    detail: str | None = None
    fields: tuple[tuple[str, str], ...] | None = None
    history_case_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.case_id is not None:
            if self.scenario_id is None:
                object.__setattr__(self, "scenario_id", self.case_id)
            if self.scenario_execution_id is None:
                object.__setattr__(self, "scenario_execution_id", self.case_id)


ProgressCallback = Callable[[ProgressEvent], None]
