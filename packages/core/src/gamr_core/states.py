from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    DISCOVERING = "discovering"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    EVALUATING = "evaluating"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class ExecutionOutcome(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class SecurityVerdict(StrEnum):
    VULNERABLE = "vulnerable"
    PROTECTED = "protected"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


class ObjectiveStatus(StrEnum):
    ACHIEVED = "achieved"
    NOT_ACHIEVED = "not_achieved"
    PARTIAL = "partial"
    NOT_ATTEMPTED = "not_attempted"
    UNKNOWN = "unknown"


_ALLOWED: dict[RunState, set[RunState]] = {
    RunState.QUEUED: {RunState.PREPARING, RunState.CANCELLED, RunState.INTERRUPTED},
    RunState.PREPARING: {
        RunState.DISCOVERING,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    },
    RunState.DISCOVERING: {
        RunState.RUNNING,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    },
    RunState.RUNNING: {
        RunState.WAITING_FOR_APPROVAL,
        RunState.EVALUATING,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    },
    RunState.WAITING_FOR_APPROVAL: {RunState.QUEUED, RunState.CANCELLED, RunState.INTERRUPTED},
    RunState.EVALUATING: {
        RunState.REPORTING,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    },
    RunState.REPORTING: {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    },
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
    RunState.INTERRUPTED: {RunState.QUEUED, RunState.FAILED},
}


def can_transition(source: RunState, target: RunState) -> bool:
    return target in _ALLOWED[source]


def transition(source: RunState, target: RunState) -> RunState:
    if not can_transition(source, target):
        raise ValueError(f"invalid run transition: {source} -> {target}")
    return target
