from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Outcome = Literal["passed", "failed", "pending", "inconclusive"]
RunState = Literal["queued", "running", "passed", "failed", "pending", "inconclusive", "error"]
ActionMode = Literal["read_only", "approval_required"]
TERMINAL = frozenset({"passed", "failed", "inconclusive", "error"})


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    query: str = Field(min_length=1, max_length=4000)
    expectation: str = Field(min_length=1, max_length=4000)


class BenignScenario(Contract):
    schema_version: Literal["1"] = "1"
    id: str = Field(default_factory=lambda: str(uuid4()), pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=200)
    original_input: str = Field(min_length=1, max_length=20000)
    workspace: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    participants: list[str] = Field(min_length=1, max_length=20)
    timezone: str
    reference_time: AwareDatetime
    stimulus: str = Field(min_length=1, max_length=10000)
    require_bridge: bool = False
    checks: list[Check] = Field(default_factory=list, max_length=10)
    questions: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=360, ge=10, le=1800)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", p) for p in self.participants):
            raise ValueError("participants must be workspace aliases")
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Use an IANA timezone") from exc
        if self.workspace not in self.participants:
            raise ValueError("participants must include workspace")
        if len({check.id for check in self.checks}) != len(self.checks):
            raise ValueError("check IDs must be unique")
        if len(set(self.participants)) != len(self.participants):
            raise ValueError("participants must be unique")
        return self


class Submission(Contract):
    scenarios: list[BenignScenario] = Field(min_length=1, max_length=100)
    repeat: int = Field(default=1, ge=1, le=100)
    concurrency: int = Field(default=1, ge=1, le=8)
    action_mode: ActionMode = "read_only"
    confirmed: bool = False

    @model_validator(mode="after")
    def approved(self) -> Self:
        if self.action_mode == "approval_required" and not self.confirmed:
            raise ValueError("explicit action confirmation is required")
        if any(scenario.questions for scenario in self.scenarios):
            raise ValueError("Resolve scenario questions before running")
        if self.action_mode == "read_only" and any(
            scenario.require_bridge or len(scenario.participants) > 1
            for scenario in self.scenarios
        ):
            raise ValueError("cross-workspace scenarios require approval-gated action mode")
        if len(self.scenarios) * self.repeat > 1000:
            raise ValueError("A batch supports at most 1000 runs")
        return self


class Finding(Contract):
    stage: str
    actor: str
    outcome: Outcome
    observation: str
    evidence: str
    quote: str = Field(min_length=1)
    hypothesis: str = ""


class Assessment(Contract):
    outcome: Outcome
    summary: str
    findings: list[Finding]


class BenignRun(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()), pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    batch_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    scenario: BenignScenario
    action_mode: ActionMode = "read_only"
    confirmed: bool = False
    concurrency: int = Field(default=1, ge=1, le=8)
    state: RunState = "queued"
    phase: str = "queued"
    summary: str = ""
    assessment: Assessment | None = None
    observations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    checkpoints: dict[str, dict[str, Any]] = Field(default_factory=dict)
