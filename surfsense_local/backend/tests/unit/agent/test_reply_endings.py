"""How an agent reply ended, read back from what opencode stored and what SurfSense noted.

The shapes are opencode 2.1.2's: a turn it finished closes with an `idle`
message naming the outcome; a declined approval or a quit leaves none, and a
turn read back from 1.x has none either.
"""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import reply_id, thread_turns

pytestmark = pytest.mark.unit

ABORTED = {"type": "aborted", "message": "Step interrupted"}


def _session(step: dict[str, Any], outcome: dict[str, Any] | None) -> list[dict]:
    """One turn: the user's question, a step that wrote "Partial words", and how it ended."""
    messages: list[dict[str, Any]] = [
        {"id": "u1", "type": "user", "text": "Go", "time": {"created": 1}},
        {
            "id": "a1",
            "type": "assistant",
            "content": [{"type": "text", "text": "Partial words"}],
            **step,
        },
    ]
    if outcome is not None:
        messages.append({"id": "i1", "type": "idle", **outcome})
    return messages


def _ending(
    step: dict[str, Any],
    outcome: dict[str, Any] | None = None,
    recorded: dict[str, dict[str, Any]] | None = None,
    answering: bool = False,
) -> dict[str, Any] | None:
    turns = thread_turns(_session(step, outcome), [], recorded or {}, answering)
    return turns[-1]["content"].get("ending")


DONE = {"time": {"created": 2, "completed": 3}}
STOPPED_STEP = {**DONE, "finish": "error", "error": ABORTED}


def test_a_stop_surfsense_noted_reads_as_stopped() -> None:
    """The user ended it: no banner, as a stopped chat reply."""
    noted = {reply_id("u1"): {"type": "stopped"}}

    ending = _ending(STOPPED_STEP, {"outcome": "interrupted"}, noted)

    assert ending == {"type": "stopped"}


def test_an_interruption_with_no_note_was_the_app_going_away() -> None:
    """opencode records a quit as it records a Stop, but SurfSense noted nothing."""
    assert _ending(STOPPED_STEP, {"outcome": "interrupted"}) == {"type": "interrupted"}


def test_a_turn_opencode_left_without_an_outcome_was_cut_off() -> None:
    """A declined approval or a quit mid-step closes nothing."""
    assert _ending(STOPPED_STEP) == {"type": "interrupted"}
    assert _ending({"time": {"created": 2}}) == {"type": "interrupted"}


def test_a_reply_still_being_written_has_no_ending_yet() -> None:
    """Unfinished because it is running, not because it was cut off."""
    assert _ending({"time": {"created": 2}}, answering=True) is None


def test_a_failure_reads_as_the_error_the_live_turn_showed() -> None:
    """Stored as the live stream labels it, so a reload changes nothing."""
    failure = {"type": "provider.error", "message": "The provider refused it"}

    ending = _ending(DONE, {"outcome": "failed", "error": failure})

    assert ending == {
        "type": "error",
        "kind": "unknown",
        "message": "The provider refused it",
    }


def test_a_finished_reply_has_no_ending() -> None:
    """Only a reply that stopped early carries an ending."""
    assert _ending(DONE, {"outcome": "succeeded"}) is None


def test_a_turn_read_back_from_1x_ends_as_its_last_step_did() -> None:
    """1.x recorded no outcome: a step it finished is a finished reply, an error stays one."""
    failure = {"type": "provider.error", "message": "The provider refused it"}

    assert _ending(DONE) is None
    assert _ending({**DONE, "error": failure}) == {
        "type": "error",
        "kind": "unknown",
        "message": "The provider refused it",
    }


def _refused_by_plan(code: str) -> dict[str, Any]:
    """opencode's record of a request SurfSense's relay refused for the plan."""
    return {
        "type": "provider.error",
        "message": "Your ChatGPT plan's limit is reached.",
        "status": 403,
        "response": {"body": f'{{"error": {{"message": "limit", "code": "{code}"}}}}'},
    }


@pytest.mark.parametrize("kind", ["subscription_limit", "subscription_sign_in"])
def test_a_plan_refusal_reads_as_the_chats_own_kind(kind: str) -> None:
    """The same notice and action as a chat reply on the plan."""
    ending = _ending(DONE, {"outcome": "failed", "error": _refused_by_plan(kind)})

    assert ending is not None and ending["kind"] == kind


def test_a_live_plan_refusal_shows_the_same_kind() -> None:
    """Read live or read back, the turn ends the same way."""
    from modules.agent.agent_threads.turn_frames import TurnFrames
    from modules.agent.opencode_client import Event

    frames = TurnFrames("ses_1")
    opened = {"sessionID": "ses_1", "inboxID": "u1", "item": {"type": "user"}}
    frames.frames(Event(type="session.inbox.enqueued", data=opened))
    failed = {"sessionID": "ses_1", "error": _refused_by_plan("subscription_limit")}
    shown = frames.frames(Event(type="session.execution.failed", data=failed))

    assert [(f["type"], f["kind"]) for f in shown] == [("error", "subscription_limit")]
