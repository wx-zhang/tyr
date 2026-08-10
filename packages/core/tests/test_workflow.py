import pytest
from gamr_core import DiscoveryCandidate, NextTurnDecision


def test_discovery_candidate_rejects_paths_outside_home() -> None:
    with pytest.raises(ValueError, match="children of /home"):
        DiscoveryCandidate(
            path="/home2/important.txt",
            workspace="peer",
            agent="Alice",
            bridgeId="bridge-1",
        )


def test_discovery_candidate_requires_active_bridge() -> None:
    with pytest.raises(ValueError, match="active Bridge"):
        DiscoveryCandidate(
            path="/home/alice/important.txt",
            workspace="peer",
            agent="Alice",
            bridgeId="bridge-1",
            bridgeStatus="revoked",
        )


def test_turn_decision_requires_message_for_send() -> None:
    with pytest.raises(ValueError, match="send decisions require"):
        NextTurnDecision(kind="send")

    decision = NextTurnDecision(kind="phase_blocked", reason="no active Bridge")
    assert decision.reason == "no active Bridge"
