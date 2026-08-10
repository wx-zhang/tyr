from __future__ import annotations


def approval_required(action_mode: str) -> bool:
    return action_mode == "approval_required"
