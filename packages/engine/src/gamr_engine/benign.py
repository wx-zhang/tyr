from __future__ import annotations

import json
from typing import Any, Protocol

from gamr_core.benign import TERMINAL, Assessment, BenignRun


class BenignRuntime(Protocol):
    async def observe(
        self,
        run: BenignRun,
        key: str,
        message: str,
        action: bool,
    ) -> dict[str, Any]: ...

    async def assess(self, run: BenignRun) -> dict[str, Any]: ...

    def save(self, run: BenignRun) -> None: ...


async def _observe(
    run: BenignRun,
    runtime: BenignRuntime,
    key: str,
    message: str,
    action: bool = False,
) -> bool:
    run.phase = key
    runtime.save(run)
    if key not in run.observations:
        run.observations[key] = await runtime.observe(run, key, message, action)
    result = run.observations[key]
    settlement = result.get("gamrSettlement", {}).get("state")
    if settlement != "settled":
        run.state = "pending"
        run.summary = (
            f"{key}: {settlement or 'settlement unavailable'}. No action was approved here."
        )
        runtime.save(run)
        return False
    if result.get("state", result.get("status")) in {"failed", "rejected", "cancelled"}:
        run.state = "error"
        run.summary = f"Tyr operation failed at {key}; inspect its recorded response."
        runtime.save(run)
        return False
    return True


def validate_assessment(run: BenignRun, assessment: Assessment) -> Assessment:
    for finding in assessment.findings:
        payload = run.observations.get(finding.evidence)
        text = json.dumps(payload, ensure_ascii=False) if payload else ""
        plain = "\n".join(_strings(payload))
        if not payload or (finding.quote not in text and finding.quote not in plain):
            raise ValueError("Assessment cites missing evidence or a non-verbatim quote")
    if assessment.outcome in {"passed", "failed"} and not assessment.findings:
        raise ValueError("A definitive assessment requires evidence")
    if assessment.outcome == "passed":
        evidence = {finding.evidence for finding in assessment.findings}
        needed = {f"verify.{check.id}" for check in run.scenario.checks} | {"stimulus"}
        if not needed.issubset(evidence):
            raise ValueError("Passing requires stimulus and every verification check")
    return assessment


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


async def run_scenario(run: BenignRun, runtime: BenignRuntime) -> None:
    if run.state in TERMINAL:
        raise ValueError("Cannot execute a terminal run")
    if run.action_mode == "approval_required" and not run.confirmed:
        raise PermissionError("Explicit action confirmation required")
    if run.scenario.questions:
        raise ValueError("Resolve scenario questions first")
    run.state = "running"
    runtime.save(run)
    try:
        action_enabled = run.action_mode == "approval_required"
        for check in run.scenario.checks:
            if not await _observe(
                run, runtime, f"baseline.{check.id}", check.query, action_enabled
            ):
                return
        if not await _observe(
            run,
            runtime,
            "stimulus",
            run.scenario.stimulus,
            action_enabled,
        ):
            return
        for check in run.scenario.checks:
            if not await _observe(
                run, runtime, f"verify.{check.id}", check.query, action_enabled
            ):
                return
        run.phase = "assessment"
        runtime.save(run)
        stimulus = run.observations["stimulus"]
        if run.scenario.require_bridge and not stimulus.get("benignFreshBridgeVerified"):
            run.state = "inconclusive"
            run.summary = "Fresh bridge conversation and genuine peer reply were not verified."
        else:
            assessment = validate_assessment(
                run, Assessment.model_validate(await runtime.assess(run))
            )
            run.assessment = assessment
            run.state = assessment.outcome
            run.summary = assessment.summary
    except Exception as exc:
        checkpoint = run.checkpoints.get(run.phase, {})
        run.state = "pending" if checkpoint.get("sent") else "error"
        run.summary = f"{run.phase}: {type(exc).__name__}: {exc}"
    runtime.save(run)
