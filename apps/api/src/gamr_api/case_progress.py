from gamr_core import ActivityType, RunActivity

_CASE_STATES = {
    "pending": "pending",
    "case_queued": "queued",
    "queued": "queued",
    "case_started": "active",
    "active": "active",
    "running": "active",
    "assessment_started": "assessing",
    "assessment_completed": "assessing",
    "assessing": "assessing",
    "assessment": "assessing",
    "case_completed": "completed",
    "completed": "completed",
    "failed": "failed",
    "blocked": "blocked",
    "cancelled": "cancelled",
}


def normalize_case_state(status: str, fallback: str = "pending") -> str:
    return _CASE_STATES.get(status, fallback)


def case_state_after_activity(current: str, activity: RunActivity) -> str:
    if activity.activity_type not in {ActivityType.CASE, ActivityType.FINDING}:
        return current
    return normalize_case_state(activity.status, current)
