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


class AssessmentStatus(StrEnum):
    UNKNOWN = "unknown"
    VALID = "valid"
    RECOVERED = "recovered"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssessmentReasonCode(StrEnum):
    SIDE_EFFECT_AFTER_APPROVAL = "side_effect_after_approval"
    SIDE_EFFECT_WITHOUT_APPROVAL = "side_effect_without_approval"
    POLICY_BLOCKED_BEFORE_SIDE_EFFECT = "policy_blocked_before_side_effect"
    SIDE_EFFECT_OCCURRED = "side_effect_occurred"
    REMOTE_ACTION_FAILED = "remote_action_failed"
    APPROVAL_STATE_UNKNOWN = "approval_state_unknown"
    SIDE_EFFECT_STATE_UNKNOWN = "side_effect_state_unknown"
    PREREQUISITE_UNAVAILABLE = "prerequisite_unavailable"
    COLLECTOR_VERIFIED = "collector_verified"
    COLLECTOR_UNAVAILABLE = "collector_unavailable"
    COLLECTOR_FAILED = "collector_failed"
    REFERENCE_CONTENT_OVERLAP = "reference_content_overlap"
    REFERENCE_CONTENT_NOT_FOUND = "reference_content_not_found"
    REFERENCE_CONTENT_UNAVAILABLE = "reference_content_unavailable"


class ContentOverlapStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    CONFIRMED = "confirmed"
    NOT_FOUND = "not_found"
    INCONCLUSIVE = "inconclusive"


class ContentMatchType(StrEnum):
    EXACT = "exact"
    REFORMATTED = "reformatted"
    ENCODED = "encoded"
    VISUAL = "visual"


class DecodingStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecodingFailureCode(StrEnum):
    INVALID_AGENT_RESPONSE = "invalid_agent_response"
    UNKNOWN_TOOL_OR_INPUT = "unknown_tool_or_input"
    INPUT_VALIDATION = "input_validation"
    ATTEMPT_EXHAUSTION = "attempt_exhaustion"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    UNSAFE_ISOLATION = "unsafe_isolation"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    UNAVAILABLE_IMPORT = "unavailable_import"
    EMPTY_OUTPUT = "empty_output"
    INVALID_OUTPUT_TREE = "invalid_output_tree"
    AMBIGUOUS_LINEAGE = "ambiguous_lineage"
    PREPARATION_FAILURE = "preparation_failure"



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
