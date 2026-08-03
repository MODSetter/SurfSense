from __future__ import annotations

import json

import pytest

from app.services.streaming.events.error import format_error
from app.tasks.chat.streaming.errors.messages import (
    CHAT_ERROR_MESSAGES,
    chat_error_message,
)

pytestmark = pytest.mark.unit


def test_every_backend_chat_error_has_display_copy() -> None:
    expected_codes = {
        "MESSAGE_PERSIST_FAILED",
        "MODEL_AUTH_FAILED",
        "MODEL_CONTEXT_LIMIT",
        "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT",
        "MODEL_NOT_FOUND",
        "MODEL_PROVIDER_UNAVAILABLE",
        "NO_ACTIVE_TURN",
        "PREMIUM_QUOTA_EXHAUSTED",
        "RATE_LIMITED",
        "SERVER_ERROR",
        "THREAD_BUSY",
        "TOOL_EXECUTION_ERROR",
        "TURN_CANCELLING",
    }

    assert set(CHAT_ERROR_MESSAGES) == expected_codes
    assert all(chat_error_message(code).strip() for code in expected_codes)


def test_lm_studio_context_error_uses_actionable_variant() -> None:
    message = chat_error_message(
        "MODEL_CONTEXT_LIMIT",
        details={"provider_error_type": "exceed_context_size_error"},
    )

    assert "LM Studio" in message


def test_error_wire_separates_display_message_from_diagnostic() -> None:
    frame = format_error(
        chat_error_message("SERVER_ERROR"),
        error_code="SERVER_ERROR",
        diagnostic="RuntimeError: database exploded",
        extra={
            "message": "unsafe override",
            "errorCode": "WRONG_CODE",
            "diagnostic": "unsafe diagnostic",
        },
    )
    payload = json.loads(frame.removeprefix("data: ").strip())

    assert payload == {
        "type": "error",
        "message": chat_error_message("SERVER_ERROR"),
        "errorCode": "SERVER_ERROR",
        "diagnostic": "RuntimeError: database exploded",
    }
    assert "errorText" not in payload


def test_unknown_backend_chat_error_cannot_be_emitted_silently() -> None:
    with pytest.raises(ValueError, match="No user-facing message registered"):
        chat_error_message("TYPO_ERROR_CODE")

