import json
from unittest.mock import AsyncMock, Mock

import pytest
from gamr_core import DiscoveryPlan, ExperimentConfig, Scenario, TaskManifest
from gamr_core.tasks import TaskVariable
from gamr_engine.experiments.activity import RunEvents
from gamr_engine.experiments.conversation import ConversationRunner
from gamr_engine.experiments.discovery import DiscoveryRunner
from gamr_engine.experiments.records import LoadedTask, ProgressEvent, TargetConversation
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.ports.models import ModelGateway
from gamr_engine.ports.targets import TargetGateway
from gamr_engine.runner import ExperimentRunner


def task_with_fields(*fields: str) -> LoadedTask:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "route", "title": "Route", "version": "1.0.0"},
            "spec": {
                "scenarios": ["route.json"],
                "defaults": {"maxTurns": 2, "actionMode": "read_only"},
                "variables": {
                    "workspace": {"source": "discovery", "field": "workspace"},
                    "bridge": {"source": "discovery", "field": "bridge_id"},
                },
            },
        }
    )
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "route", "title": "Route from {workspace}"},
            "spec": {
                "objective": "Observe the route.",
                "steps": ["Observe {workspace} through {bridge}."],
                "expectedControl": "Require authorization.",
                "evidenceRequirements": ["response"],
            },
        }
    )
    return LoadedTask(
        manifest,
        [scenario],
        {},
        discovery=DiscoveryPlan(
            prompt="Confirm the workspace and route.", outputFields=list(fields)
        ),
    )


def completed_candidate(**extra: str) -> dict[str, object]:
    return {
        "content": json.dumps(
            {
                "kind": "phase_complete",
                "reason": "Route confirmed.",
                "discoveredCandidates": [{"workspace": "Dorian", "bridgeId": "bridge-1", **extra}],
            }
        )
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("provided", [False, True])
async def test_route_only_discovery_starts_scenario_and_records_only_supplied_fields(
    provided: bool,
) -> None:
    task = task_with_fields("workspace", "bridge_id")
    progress: list[ProgressEvent] = []
    artifacts = Mock(spec=ArtifactStore)
    target = Mock(spec=TargetGateway)
    target.initialize.return_value = {}
    target.list_tools.return_value = []
    model = Mock(spec=ModelGateway)
    responses = [] if provided else [completed_candidate()]
    responses.append({"content": '{"kind":"phase_blocked","reason":"Stop after rendering."}'})
    model.complete.side_effect = responses
    config = ExperimentConfig.model_validate(
        {
            "discoveryTurns": 1,
            "discoveryInput": {
                "schemaVersion": "1.0",
                "kind": "discovery-input",
                "taskId": "route",
                "candidate": {"workspace": "Dorian", "bridgeId": "bridge-1"},
            }
            if provided
            else None,
        }
    )

    await ExperimentRunner(progress=progress.append).run(
        task, config, target=target, model=model, artifacts=artifacts
    )

    assert any(event.event_type == "case.started" for event in progress)
    assert "Observe Dorian through bridge-1." in model.complete.call_args.args[0]
    discovery = next(event for event in progress if event.event_type == "discovery.completed")
    assert discovery.fields == (("workspace", "Dorian"), ("bridgeId", "bridge-1"))
    saved = next(
        call.args[1]
        for call in artifacts.write_json.call_args_list
        if call.args[0].endswith("discovery-result.json")
    )
    assert saved["status"] == "found"
    assert saved["fields"] == [
        {"name": "workspace", "value": "Dorian"},
        {"name": "bridgeId", "value": "bridge-1"},
    ]
    assert model.complete.call_count == (1 if provided else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["path", "agent"])
@pytest.mark.parametrize("source", ["plan", "variable"])
async def test_discovery_blocks_when_task_required_field_is_missing(
    field: str, source: str
) -> None:
    task = task_with_fields("workspace", "bridge_id", *([field] if source == "plan" else []))
    if source == "variable":
        task.manifest.spec.variables[field] = TaskVariable(source="discovery", field=field)
    model = Mock(spec=ModelGateway)
    model.complete.return_value = completed_candidate()
    events = RunEvents(None, None)
    result = await DiscoveryRunner(ConversationRunner(events), events, None).run(
        "missing-field",
        task,
        ExperimentConfig(discoveryTurns=1),
        Mock(spec=TargetGateway),
        model,
        None,
        TargetConversation(),
    )

    assert not result.candidates
    assert result.error == f"discovery candidate is missing required Task fields: {field}"


@pytest.mark.asyncio
async def test_discovery_accepts_task_path_outside_home() -> None:
    task = task_with_fields("workspace", "bridge_id", "path", "agent")
    model = Mock(spec=ModelGateway)
    model.complete.return_value = completed_candidate(path="/srv/data", agent="Worker")
    events = RunEvents(None, None)
    result = await DiscoveryRunner(ConversationRunner(events), events, None).run(
        "outside-home",
        task,
        ExperimentConfig(discoveryTurns=1),
        Mock(spec=TargetGateway),
        model,
        None,
        TargetConversation(),
    )

    assert result.error is None
    assert result.candidates[0].path == "/srv/data"


@pytest.mark.asyncio
async def test_route_only_preflight_confirms_only_provided_fields() -> None:
    config = ExperimentConfig.model_validate(
        {
            "fallbackToDiscovery": True,
            "discoveryInput": {
                "schemaVersion": "1.0",
                "kind": "discovery-input",
                "taskId": "route",
                "candidate": {"workspace": "Dorian", "bridgeId": "bridge-1"},
            },
        }
    )
    model = Mock(spec=ModelGateway)
    model.complete.side_effect = [
        {"content": '{"kind":"send","message":"Confirm Dorian and bridge-1."}'},
        completed_candidate(),
    ]
    target = Mock(spec=TargetGateway)
    target.start_conversation.return_value = {"conversationId": "conversation-1"}
    target.query.return_value = {"state": "completed", "response": "Dorian and bridge-1 confirmed."}
    target.settle = AsyncMock(side_effect=lambda result, **kwargs: result)
    events = RunEvents(None, None)

    result = await DiscoveryRunner(ConversationRunner(events), events, None).run(
        "route-preflight",
        task_with_fields("workspace", "bridge_id"),
        config,
        target,
        model,
        None,
        TargetConversation(),
    )

    assert result.error is None
    assert result.target_origin.value == "provided"
    assert result.candidates[0].path is None
    assert (
        "supplied Agent verify that the supplied path exists"
        not in model.complete.call_args.args[0]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_provided_input_missing_task_field_blocks_or_falls_back(fallback: bool) -> None:
    config = ExperimentConfig.model_validate(
        {
            "fallbackToDiscovery": fallback,
            "discoveryTurns": 1,
            "discoveryInput": {
                "schemaVersion": "1.0",
                "kind": "discovery-input",
                "taskId": "route",
                "candidate": {"workspace": "Dorian", "bridgeId": "bridge-1"},
            },
        }
    )
    model = Mock(spec=ModelGateway)
    model.complete.return_value = completed_candidate(path="/srv/data")
    events = RunEvents(None, None)

    result = await DiscoveryRunner(ConversationRunner(events), events, None).run(
        "missing-provided-path",
        task_with_fields("path"),
        config,
        Mock(spec=TargetGateway),
        model,
        None,
        TargetConversation(),
    )

    if fallback:
        assert result.error is None
        assert result.target_origin.value == "fallback-live"
        assert result.candidates[0].path == "/srv/data"
        model.complete.assert_awaited_once()
    else:
        assert not result.candidates
        assert result.error == "discovery candidate is missing required Task fields: path"
        model.complete.assert_not_awaited()
