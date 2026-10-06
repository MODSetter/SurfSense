"""How an agent reply ended, read back from what opencode stored and what SurfSense noted.

The shapes are opencode 1.18.34's, as it stores a reply cut off by an abort,
by its own exit, or by a failure.
"""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import reply_id, thread_turns

pytestmark = pytest.mark.unit

ABORTED = {"name": "MessageAbortedError", "data": {"message": "Aborted"}}


def _session(reply: dict[str, Any]) -> list[dict[str, Any]]:
    """One turn: the user's question, and a reply that wrote "Partial words"."""
    return [
        {
            "info": {"id": "u1", "role": "user", "time": {"created": 1}},
            "parts": [{"type": "text", "text": "Go"}],
        },
        {
            "info": {"id": "a1", "role": "assistant", "parentID": "u1", **reply},
            "parts": [{"type": "text", "text": "Partial words"}],
        },
    ]


def _ending(
    reply: dict[str, Any],
    recorded: dict[str, dict[str, Any]] | None = None,
    answering: bool = False,
) -> dict[str, Any] | None:
    turns = thread_turns(_session(reply), [], recorded or {}, answering)
    return turns[-1]["content"].get("ending")


def test_a_stop_surfsense_noted_reads_as_stopped() -> None:
    """The user ended it: no banner, as a stopped chat reply."""
    noted = {reply_id("u1"): {"type": "stopped"}}

    ending = _ending({"time": {"created": 2, "completed": 3}, "error": ABORTED}, noted)

    assert ending == {"type": "stopped"}


def test_an_abort_with_no_note_was_the_app_going_away() -> None:
    """A quit aborts as a Stop does, but leaves no note."""
    ending = _ending({"time": {"created": 2, "completed": 3}, "error": ABORTED})

    assert ending == {"type": "interrupted"}


def test_a_reply_opencode_never_finished_was_cut_off() -> None:
    """opencode exits on SIGTERM or a crash without marking the reply at all."""
    assert _ending({"time": {"created": 2}}) == {"type": "interrupted"}


def test_a_reply_still_being_written_has_no_ending_yet() -> None:
    """Unfinished because it is running, not because it was cut off."""
    assert _ending({"time": {"created": 2}}, answering=True) is None


def test_a_failure_reads_as_the_error_the_live_turn_showed() -> None:
    """Stored as the live stream labels it, so a reload changes nothing."""
    failure = {"name": "APIError", "data": {"message": "The provider refused it"}}

    ending = _ending({"time": {"created": 2, "completed": 3}, "error": failure})

    assert ending == {
        "type": "error",
        "kind": "unknown",
        "message": "The provider refused it",
    }


def test_a_finished_reply_has_no_ending() -> None:
    """Only a reply that stopped early carries an ending."""
    assert _ending({"time": {"created": 2, "completed": 3}}) is None


def _refused_by_plan(code: str) -> dict[str, Any]:
    """opencode's record of a request SurfSense's relay refused for the plan."""
    return {
        "name": "APIError",
        "data": {
            "message": "Your ChatGPT plan's limit is reached.",
            "statusCode": 403,
            "isRetryable": False,
            "responseBody": f'{{"error": {{"message": "limit", "code": "{code}"}}}}',
        },
    }


@pytest.mark.parametrize("kind", ["subscription_limit", "subscription_sign_in"])
def test_a_plan_refusal_reads_as_the_chats_own_kind(kind: str) -> None:
    """The same notice and action as a chat reply on the plan."""
    ending = _ending(
        {"time": {"created": 2, "completed": 3}, "error": _refused_by_plan(kind)}
    )

    assert ending is not None and ending["kind"] == kind


def test_a_live_plan_refusal_shows_the_same_kind() -> None:
    """Read live or read back, the turn ends the same way."""
    from modules.agent.agent_threads.turn_frames import TurnFrames
    from modules.agent.opencode_client import Event

    frames = TurnFrames("ses_1")
    user = {"sessionID": "ses_1", "info": {"id": "u1", "role": "user"}}
    frames.frames(Event(type="message.updated", properties=user))
    failed = {"sessionID": "ses_1", "error": _refused_by_plan("subscription_limit")}
    shown = frames.frames(Event(type="session.error", properties=failed))

    assert [(f["type"], f["kind"]) for f in shown] == [("error", "subscription_limit")]
