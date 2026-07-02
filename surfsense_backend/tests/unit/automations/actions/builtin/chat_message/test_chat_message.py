"""Pure-logic unit tests for the ``chat_message`` action.

Only the infra-free contract lives here: the action self-registers, and its
params model requires ``thread_id`` + ``message`` and forbids extras. The
run-time behavior (the in-flight guard against real ``ChatSessionState`` and
streaming under system auth) is proven in
``tests/integration/automations/actions/builtin/chat_message/test_chat_message.py``,
against real persistence rather than a faked ``get_session_state``/``stream_new_chat``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_chat_message_action_is_registered_after_package_import() -> None:
    import app.automations  # noqa: F401  (force side-effect registrations)
    from app.automations.actions.store import get_action

    definition = get_action("chat_message")

    assert definition is not None
    assert definition.type == "chat_message"


def test_params_require_thread_id_and_message_and_forbid_extra() -> None:
    from pydantic import ValidationError

    from app.automations.actions.builtin.chat_message.params import (
        ChatMessageActionParams,
    )

    ok = ChatMessageActionParams.model_validate({"thread_id": 7, "message": "hi"})
    assert ok.thread_id == 7
    assert ok.message == "hi"

    with pytest.raises(ValidationError):
        ChatMessageActionParams.model_validate({"thread_id": 7, "message": ""})

    with pytest.raises(ValidationError):
        ChatMessageActionParams.model_validate({"thread_id": 7})

    with pytest.raises(ValidationError):
        ChatMessageActionParams.model_validate(
            {"thread_id": 7, "message": "hi", "surprise": True}
        )
