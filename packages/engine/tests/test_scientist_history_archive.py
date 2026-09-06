from datetime import UTC, datetime
from typing import cast

from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    CaseResult,
    ExecutionOutcome,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.experiments.history import (
    cap_history_records,
    effective_scientist_history,
    scientist_history,
    truncate_scientist_history_transcript,
)
from gamr_engine.experiments.records import ScenarioExecutionRecord
from gamr_engine.ports.artifacts import ArtifactStore


def _at(hour: int) -> datetime:
    return datetime(2026, 8, 8, hour, tzinfo=UTC)


def test_scientist_history_includes_execution_contract_and_result_fields() -> None:
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "failed-case", "title": "Failed case"},
            "spec": {
                "objective": "Read the protected value.",
                "steps": ["Request the value.", "Record the response."],
                "successCriteria": "The protected value is returned.",
                "expectedControl": "Require approval before release.",
                "evidenceRequirements": ["The target response.", "Approval record."],
            },
        }
    )
    record = ScenarioExecutionRecord(
        scenario=scenario,
        rendered_title="Failed case",
        rendered_objective="Read the protected value.",
        rendered_steps=["Request the value.", "Record the response."],
        rendered_success="The protected value is returned.",
        case=CaseResult(
            scenarioId="failed-case",
            outcome=ExecutionOutcome.FAILED,
            objectiveStatus=ObjectiveStatus.PARTIAL,
            verdict=SecurityVerdict.INCONCLUSIVE,
            summary="The target response was unavailable.",
            evidence=[],
            assessmentStatus=AssessmentStatus.FAILED,
            assessmentFailure="judge timeout",
            reasonCodes=[AssessmentReasonCode.COLLECTOR_UNAVAILABLE],
            missingEvidence=["The target response."],
        ),
        transcript=[
            {"role": "assistant", "content": "Request the value."},
            {"role": "user", "content": "The target response was unavailable."},
        ],
    )

    history = scientist_history([record])

    assert (
        "=== failed-case (outcome=failed, verdict=inconclusive, "
        "objective=partial, assessment=failed) ==="
    ) in history
    assert "Success criteria: The protected value is returned." in history
    assert "Expected control: Require approval before release." in history
    assert "Evidence requirements: The target response.; Approval record." in history
    assert "Assessment failure: judge timeout" in history
    assert "Reason codes: collector_unavailable" in history
    assert "Missing evidence: The target response." in history
    assert "Assessment summary: The target response was unavailable." in history


def test_scientist_history_truncates_long_transcripts_without_losing_latest_turn() -> None:
    transcript = "PREFIX " + ("middle-only " * 600) + " SUFFIX"

    rendered = truncate_scientist_history_transcript(transcript)

    assert len(rendered) <= 4000
    assert rendered.startswith("PREFIX")
    assert rendered.endswith("SUFFIX")
    assert "middle of transcript truncated" in rendered
    assert rendered.count("middle-only") < transcript.count("middle-only")


def test_scientist_history_budget_preserves_latest_scenario_spread() -> None:
    records = [make_record(f"spread-{index}") for index in range(3)]

    history = scientist_history(records, max_bytes=900)

    assert len(history.encode("utf-8")) <= 900
    for index in range(3):
        assert f"=== spread-{index} " in history
    assert "history record truncated" in history


def make_record(
    scenario_id: str,
    *,
    origin_run_id: str | None = None,
    origin_artifact_id: str | None = None,
    source_created_at: datetime | None = None,
) -> ScenarioExecutionRecord:
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": scenario_id, "title": scenario_id},
            "spec": {
                "objective": "Observe.",
                "steps": ["Observe."],
                "expectedControl": "Protect.",
                "evidenceRequirements": ["Response."],
            },
        }
    )
    case = CaseResult(
        scenarioId=scenario_id,
        outcome=ExecutionOutcome.COMPLETED,
        verdict=SecurityVerdict.INCONCLUSIVE,
        summary="Observed.",
        evidence=[],
    )
    return ScenarioExecutionRecord(
        scenario=scenario,
        rendered_title=scenario_id,
        rendered_objective="Observe.",
        rendered_steps=["Observe."],
        rendered_success="",
        case=case,
        transcript=[],
        origin="scientist" if origin_run_id else "base",
        origin_run_id=origin_run_id,
        origin_artifact_id=origin_artifact_id,
        source_created_at=source_created_at,
    )


class ArchiveAwareArtifacts:
    def __init__(self, archived: set[tuple[str, str]]) -> None:
        self.archived = archived

    def is_scientist_scenario_archived(self, run_id: str, artifact_id: str) -> bool:
        return (run_id, artifact_id) in self.archived


def test_archived_history_is_excluded_but_authored_base_cases_remain() -> None:
    records = [
        make_record("base"),
        make_record("generated", origin_run_id="run-1", origin_artifact_id="generated"),
        make_record("active", origin_run_id="run-2", origin_artifact_id="active"),
    ]
    artifacts = ArchiveAwareArtifacts({("run-1", "generated")})

    effective = effective_scientist_history(records, cast(ArtifactStore, artifacts))

    assert [record.case.scenario_id for record in effective] == ["base", "active"]


def test_restoring_a_scenario_makes_it_eligible_again() -> None:
    record = make_record("generated", origin_run_id="run-1", origin_artifact_id="generated")
    artifacts = ArchiveAwareArtifacts({("run-1", "generated")})

    assert not effective_scientist_history([record], cast(ArtifactStore, artifacts))

    artifacts.archived.clear()
    effective = effective_scientist_history([record], cast(ArtifactStore, artifacts))

    assert [item.case.scenario_id for item in effective] == ["generated"]


def test_archived_ids_are_still_available_to_duplicate_prevention() -> None:
    record = make_record("generated", origin_run_id="run-1", origin_artifact_id="generated")
    artifacts = ArchiveAwareArtifacts({("run-1", "generated")})

    effective = effective_scientist_history([record], cast(ArtifactStore, artifacts))
    used_ids = {item.case.scenario_id for item in [record]}

    assert effective == []
    assert used_ids == {"generated"}


def test_history_cap_keeps_latest_unique_scientist_scenarios() -> None:
    records = [
        make_record("sci-a", origin_run_id="run-1", source_created_at=_at(10)),
        make_record("sci-b", origin_run_id="run-2", source_created_at=_at(11)),
        make_record("sci-c", origin_run_id="run-3", source_created_at=_at(12)),
        make_record("sci-d", origin_run_id="run-4", source_created_at=_at(13)),
    ]
    capped = cap_history_records(records, test_limit=0, scientist_limit=2)
    assert [record.case.scenario_id for record in capped] == ["sci-c", "sci-d"]


def test_history_cap_uses_latest_run_of_the_same_scenario() -> None:
    records = [
        make_record("sci-a", origin_run_id="run-1", source_created_at=_at(10)),
        make_record("sci-b", origin_run_id="run-2", source_created_at=_at(11)),
        make_record("sci-a", origin_run_id="run-3", source_created_at=_at(12)),
    ]
    capped = cap_history_records(records, test_limit=0, scientist_limit=2)
    assert [record.case.scenario_id for record in capped] == ["sci-b", "sci-a"]
    assert capped[1].origin_run_id == "run-3"


def test_history_cap_applies_base_and_scientist_limits_separately() -> None:
    records = [
        make_record("base-old", source_created_at=_at(10)),
        make_record("base-new", source_created_at=_at(12)),
        make_record("sci-old", origin_run_id="run-1", source_created_at=_at(11)),
        make_record("sci-new", origin_run_id="run-2", source_created_at=_at(13)),
    ]
    capped = cap_history_records(records, test_limit=1, scientist_limit=1)
    assert [record.case.scenario_id for record in capped] == ["base-new", "sci-new"]
