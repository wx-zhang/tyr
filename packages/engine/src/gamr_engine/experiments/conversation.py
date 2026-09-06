from __future__ import annotations

from gamr_core import ExperimentPresetConfig

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.targets import TargetGateway
from .activity import RunEvents
from .conversation_state import ConversationState, TurnContext, turn_prompt
from .decisions import complete_decision, reject_runtime_variables
from .records import PhaseResult, TargetConversation
from .target_exchange import send_target_message
from .target_reply import record_target_reply


class ConversationRunner:
    def __init__(self, events: RunEvents) -> None:
        self._events = events

    async def run(
        self,
        phase_prompt: str,
        target: TargetGateway,
        model: ModelGateway,
        config: ExperimentPresetConfig,
        *,
        max_turns: int,
        conversation: TargetConversation,
        require_candidates: bool,
        run_id: str,
        artifacts: ArtifactStore | None,
        phase: str,
        case_id: str | None = None,
        scenario_execution_id: str | None = None,
        runtime_vars: set[str] | None = None,
    ) -> PhaseResult:
        state = ConversationState()
        for turn in range(1, max_turns + 1):
            self._events.emit(
                "model.thinking",
                run_id,
                phase=phase,
                case_id=case_id,
                turn=turn,
            )
            context = TurnContext(
                run_id,
                phase,
                case_id,
                scenario_execution_id,
                turn,
                phase_prompt,
            )
            rendered = turn_prompt(phase_prompt, state)
            parsed = await complete_decision(
                model,
                rendered,
                context,
                conversation,
                state.transcript,
                strict=require_candidates,
                events=self._events,
                artifacts=artifacts,
            )
            if isinstance(parsed, PhaseResult):
                return parsed
            if parsed is None:
                continue
            decision = parsed.decision
            if decision.kind == "phase_complete":
                self._events.emit(
                    "turn.completed",
                    run_id,
                    phase=phase,
                    case_id=case_id,
                    turn=turn,
                )
                if require_candidates and not decision.discovered_candidates:
                    return PhaseResult(
                        state.transcript,
                        conversation.operation_id,
                        decision,
                        [],
                        "discovery completed without candidates",
                    )
                return PhaseResult(
                    state.transcript,
                    conversation.operation_id,
                    decision,
                    decision.discovered_candidates,
                )
            if decision.kind == "phase_blocked":
                self._events.emit(
                    "turn.completed",
                    run_id,
                    phase=phase,
                    case_id=case_id,
                    turn=turn,
                )
                return PhaseResult(
                    state.transcript,
                    conversation.operation_id,
                    decision,
                    [],
                    decision.reason,
                )
            message = decision.message or ""
            if reject_runtime_variables(
                message,
                runtime_vars,
                context,
                state.transcript,
                artifacts=artifacts,
            ):
                continue
            exchange = await send_target_message(
                target,
                config,
                conversation,
                context,
                state.transcript,
                decision,
                parsed.content,
                events=self._events,
                artifacts=artifacts,
            )
            if isinstance(exchange, PhaseResult):
                return exchange
            settlement_error = record_target_reply(
                exchange,
                conversation,
                state,
                context,
                events=self._events,
                artifacts=artifacts,
            )
            if settlement_error is not None:
                return PhaseResult(
                    state.transcript,
                    conversation.operation_id,
                    decision,
                    [],
                    settlement_error,
                )
        return PhaseResult(
            state.transcript,
            conversation.operation_id,
            None,
            [],
            "turn budget exhausted",
        )
