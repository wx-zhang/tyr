from __future__ import annotations

import json

from gamr_core import DiscoveryCandidate, ExperimentPresetConfig, TargetOrigin

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.targets import TargetGateway
from ..ports.tracing import TracePort, trace_span
from .activity import RunEvents
from .artifacts import discovery_fields, write_discovery_result
from .conversation import ConversationRunner
from .decisions import DISCOVERY_DECISION_PROMPT
from .records import LoadedTask, PhaseResult, TargetConversation
from .rendering import methodology_prefix

_DISCOVERY_PREFLIGHT_PROMPT = (
    "- Perform a bounded availability preflight for the exact supplied target.\n"
    "- NEVER execute a Scenario step during preflight.\n"
    "- The supplied workspace, Agent, and path are in the peer workspace behind "
    "the supplied Bridge ID.\n"
    "- In the first send decision, address the peer Tyr Assistant in the supplied "
    "workspace over the supplied Bridge ID. Routing exists only in the message text, "
    "so explicitly name both.\n"
    "- Ask the peer Tyr Assistant to confirm the supplied Agent exists in that peer "
    "workspace and have the supplied Agent verify that the supplied path exists and "
    "is usable.\n"
    "- NEVER ask the current Tyr Assistant's local Agent roster or filesystem to "
    "verify the supplied Agent or path.\n"
    "- Do not accept Bridge or workspace metadata alone as confirmation of the Agent "
    "or path.\n"
    "- Return only a JSON NextTurnDecision.\n"
    "- Complete with discoveredCandidates containing the exact candidate only when "
    "Tyr's reply confirms every supplied field.\n"
    "- Use phase_blocked when Tyr's reply does not confirm every supplied field.\n"
)


class DiscoveryRunner:
    def __init__(
        self,
        conversation: ConversationRunner,
        events: RunEvents,
        trace_port: TracePort | None,
    ) -> None:
        self._conversation = conversation
        self._events = events
        self._trace_port = trace_port

    @staticmethod
    def provided_candidate(config: ExperimentPresetConfig) -> DiscoveryCandidate:
        document = config.discovery_input
        if document is None:
            raise ValueError("provided candidate requires discovery input")
        return DiscoveryCandidate(
            path=document.candidate.path,
            workspace=document.candidate.workspace,
            agent=document.candidate.agent,
            bridgeId=document.candidate.bridge_id,
        )

    @staticmethod
    def preflight_reached_target(result: PhaseResult) -> bool:
        for item in result.transcript:
            observed_facts = item.get("observedFacts")
            if not isinstance(observed_facts, str):
                continue
            facts = json.loads(observed_facts)
            if isinstance(facts, dict) and facts.get("targetState") == "completed":
                return True
        return False

    @classmethod
    def preflight_confirmed(cls, result: PhaseResult, candidate: DiscoveryCandidate) -> bool:
        return (
            result.error is None
            and bool(result.candidates)
            and cls.preflight_reached_target(result)
            and discovery_fields(result.candidates[0]) == discovery_fields(candidate)
        )

    async def run(
        self,
        run_id: str,
        task: LoadedTask,
        config: ExperimentPresetConfig,
        target: TargetGateway,
        model: ModelGateway,
        artifacts: ArtifactStore | None,
        conversation: TargetConversation,
    ) -> PhaseResult:
        with trace_span(self._trace_port, "discovery", metadata={"runId": run_id}):
            if config.discovery_input is None:
                return await self.live(
                    run_id,
                    task,
                    config,
                    target,
                    model,
                    artifacts,
                    conversation,
                    origin=TargetOrigin.LIVE,
                )
            candidate = self.provided_candidate(config)
            if not config.fallback_to_discovery:
                result = PhaseResult(
                    [], None, None, [candidate], target_origin=TargetOrigin.PROVIDED
                )
                write_discovery_result(artifacts, run_id, result)
                self._events.emit(
                    "discovery.completed",
                    run_id,
                    phase="discovery",
                    detail="provided target",
                    fields=discovery_fields(candidate),
                    metadata_extra={"targetOrigin": TargetOrigin.PROVIDED.value},
                )
                return result
            preflight = await self.preflight(run_id, config, target, model, artifacts, candidate)
            preflight_confirmed = self.preflight_confirmed(preflight, candidate)
            preflight_detail = (
                "provided target confirmed"
                if preflight_confirmed
                else (
                    "provided target unavailable"
                    if self.preflight_reached_target(preflight)
                    else "provided target preflight inconclusive"
                )
            )
            self._events.emit(
                "discovery.preflight.completed",
                run_id,
                phase="discovery",
                detail=preflight_detail,
                fields=discovery_fields(candidate),
                metadata_extra={
                    "targetOrigin": (
                        TargetOrigin.PROVIDED.value
                        if preflight_confirmed
                        else TargetOrigin.FALLBACK_LIVE.value
                    )
                },
            )
            if preflight_confirmed:
                result = PhaseResult(
                    preflight.transcript,
                    preflight.operation_id,
                    preflight.decision,
                    [candidate],
                    target_origin=TargetOrigin.PROVIDED,
                )
                write_discovery_result(artifacts, run_id, result)
                self._events.emit(
                    "discovery.completed",
                    run_id,
                    phase="discovery",
                    detail="provided target confirmed by preflight",
                    fields=discovery_fields(candidate),
                    metadata_extra={"targetOrigin": TargetOrigin.PROVIDED.value},
                )
                return result
            reason = preflight.error or "preflight could not confirm provided target"
            self._events.emit(
                "discovery.preflight.failed",
                run_id,
                phase="discovery",
                detail=reason,
                metadata_extra={"targetOrigin": TargetOrigin.FALLBACK_LIVE.value},
            )
            live = await self.live(
                run_id,
                task,
                config,
                target,
                model,
                artifacts,
                TargetConversation(),
                origin=TargetOrigin.FALLBACK_LIVE,
            )
            return PhaseResult(
                [*preflight.transcript, *live.transcript],
                live.operation_id,
                live.decision,
                live.candidates,
                live.error,
                TargetOrigin.FALLBACK_LIVE,
            )

    async def preflight(
        self,
        run_id: str,
        config: ExperimentPresetConfig,
        target: TargetGateway,
        model: ModelGateway,
        artifacts: ArtifactStore | None,
        candidate: DiscoveryCandidate,
    ) -> PhaseResult:
        self._events.emit(
            "discovery.preflight.started",
            run_id,
            phase="discovery",
            fields=discovery_fields(candidate),
            metadata_extra={"targetOrigin": TargetOrigin.PROVIDED.value},
        )
        prompt = (
            _DISCOVERY_PREFLIGHT_PROMPT
            + DISCOVERY_DECISION_PROMPT
            + "\nSupplied candidate:\n```json\n"
            + json.dumps(dict(discovery_fields(candidate)), sort_keys=True)
            + "\n```\n"
        )
        return await self._conversation.run(
            prompt,
            target,
            model,
            config,
            max_turns=min(3, config.discovery_turns),
            conversation=TargetConversation(),
            require_candidates=True,
            run_id=run_id,
            artifacts=artifacts,
            phase="discovery-preflight",
        )

    async def live(
        self,
        run_id: str,
        task: LoadedTask,
        config: ExperimentPresetConfig,
        target: TargetGateway,
        model: ModelGateway,
        artifacts: ArtifactStore | None,
        conversation: TargetConversation,
        *,
        origin: TargetOrigin,
    ) -> PhaseResult:
        if task.discovery is None:
            result = PhaseResult([], None, None, [], "task has no discovery plan", origin)
            write_discovery_result(artifacts, run_id, result)
            self._events.emit(
                "discovery.completed",
                run_id,
                phase="discovery",
                detail="blocked",
                metadata_extra={"targetOrigin": origin.value},
            )
            return result
        self._events.emit(
            "discovery.started",
            run_id,
            phase="discovery",
            metadata_extra={"targetOrigin": origin.value},
        )
        prompt = methodology_prefix(task)
        prompt += f"\nDiscovery plan:\n{task.discovery.prompt}\n"
        prompt += DISCOVERY_DECISION_PROMPT
        result = await self._conversation.run(
            prompt,
            target,
            model,
            config,
            max_turns=config.discovery_turns,
            conversation=conversation,
            require_candidates=True,
            run_id=run_id,
            artifacts=artifacts,
            phase="discovery",
        )
        result = PhaseResult(
            result.transcript,
            result.operation_id,
            result.decision,
            result.candidates,
            result.error,
            origin,
        )
        fields = discovery_fields(result.candidates[0]) if result.candidates else None
        write_discovery_result(artifacts, run_id, result)
        self._events.emit(
            "discovery.completed",
            run_id,
            phase="discovery",
            detail=f"{len(result.candidates)} candidate(s)" if result.candidates else "blocked",
            fields=fields,
            metadata_extra={"targetOrigin": origin.value},
        )
        return result
