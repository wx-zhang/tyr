import json

from gamr_engine.experiments.activity import RunEvents
from gamr_engine.experiments.conversation_state import ConversationState, TurnContext
from gamr_engine.experiments.records import ProgressEvent, TargetConversation
from gamr_engine.experiments.target_exchange import TargetExchange
from gamr_engine.experiments.target_reply import record_target_reply


def test_repeated_peer_approval_reply_preserves_status_and_turn_evidence() -> None:
    reply = "Joe workspace is waiting for approval from its own workspace owner."
    result: dict[str, object] = {
        "response": reply,
        "state": "blocked_on_peer_approval",
        "gamrSettlement": {"state": "peer_approval_blocked", "notes": []},
    }
    conversation = TargetConversation(seen_reply=reply)
    state = ConversationState()
    progress: list[ProgressEvent] = []
    error = record_target_reply(
        TargetExchange("turn-9", "Status?", "decision", "key", None, None, result),
        conversation,
        state,
        TurnContext("run", "case", "scenario", "execution", 9, "Ask Tyr."),
        events=RunEvents(progress.append, None),
        artifacts=None,
    )
    assert error is None
    assert state.transcript[-1]["content"] == reply
    assert '"settlementState":"peer_approval_blocked"' in state.transcript[-1]["observedFacts"]
    completed = next(event for event in progress if event.event_type == "target.completed")
    assert completed.detail == reply
    assert completed.fields == (("settlementState", "peer_approval_blocked"),)
    turn = progress[-1]
    assert turn.event_type == "turn.completed"
    assert turn.fields == (("settlementState", "peer_approval_blocked"),)


def test_fresh_bridge_reply_is_not_treated_as_cumulative_text() -> None:
    reply = "The request was refused."
    state = ConversationState()
    record_target_reply(
        TargetExchange(
            "turn",
            "Another request",
            "decision",
            "key",
            None,
            None,
            {
                "operationId": "operation-current",
                "response": "Working",
                "bridges": [
                    {
                        "bridgeRequestId": "bridge-previous",
                        "conversationId": "conversation-previous",
                        "state": "completed",
                        "response": "Earlier result",
                    },
                    {
                        "bridgeRequestId": "bridge-current",
                        "conversationId": "conversation-current",
                        "state": "completed",
                        "response": reply,
                    },
                ],
                "gamrSettlement": {"state": "settled", "reply": reply},
            },
        ),
        TargetConversation(seen_reply=reply),
        state,
        TurnContext("run", "case", "scenario", "execution", 2, "Ask Tyr."),
        events=RunEvents(None, None),
        artifacts=None,
    )
    assert state.transcript[-1]["content"] == reply
    assert json.loads(state.transcript[-1]["observedFacts"]) == {
        "operationId": "operation-current",
        "settlementState": "settled",
        "bridgeRequestId": "bridge-current",
        "bridgeConversationId": "conversation-current",
        "bridgeState": "completed",
        "bridgeResponseRecorded": True,
    }
