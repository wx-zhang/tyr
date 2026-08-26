from typing import cast

from gamr_core import CaseResult, ExecutionOutcome, Scenario, SecurityVerdict
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.runner import CaseRecord, ExperimentRunner


def make_record(
    scenario_id: str,
    *,
    origin_run_id: str | None = None,
    origin_artifact_id: str | None = None,
) -> CaseRecord:
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
    return CaseRecord(
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

    effective = ExperimentRunner._effective_scientist_history(
        records, cast(ArtifactStore, artifacts)
    )

    assert [record.case.scenario_id for record in effective] == ["base", "active"]


def test_restoring_a_scenario_makes_it_eligible_again() -> None:
    record = make_record("generated", origin_run_id="run-1", origin_artifact_id="generated")
    artifacts = ArchiveAwareArtifacts({("run-1", "generated")})

    assert not ExperimentRunner._effective_scientist_history(
        [record], cast(ArtifactStore, artifacts)
    )

    artifacts.archived.clear()
    effective = ExperimentRunner._effective_scientist_history(
        [record], cast(ArtifactStore, artifacts)
    )

    assert [item.case.scenario_id for item in effective] == ["generated"]


def test_archived_ids_are_still_available_to_duplicate_prevention() -> None:
    record = make_record("generated", origin_run_id="run-1", origin_artifact_id="generated")
    artifacts = ArchiveAwareArtifacts({("run-1", "generated")})

    effective = ExperimentRunner._effective_scientist_history(
        [record], cast(ArtifactStore, artifacts)
    )
    used_ids = {item.case.scenario_id for item in [record]}

    assert effective == []
    assert used_ids == {"generated"}
