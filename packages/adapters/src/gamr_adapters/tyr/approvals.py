from __future__ import annotations


class ApprovalRequiredError(RuntimeError):
    """Raised when an action has no recorded human approval."""
