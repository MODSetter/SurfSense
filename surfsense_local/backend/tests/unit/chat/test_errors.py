"""Sorting a failed generation into something the user can act on."""

import httpx
import pytest

from modules.chat.errors import ChatErrorKind, classify_chat_error
from shared.secrets import UnreadableSecretError

pytestmark = pytest.mark.unit


def test_a_key_the_app_cannot_read_asks_for_a_new_one() -> None:
    """Not `unknown`, because the fix is specific and the user can do it.

    The stored key is unrecoverable once the per install secret changes, so the
    only useful answer names the connection's key. "Something went wrong" sends
    someone looking for a bug that is not there.
    """
    # No message passed in: the condition owns its wording, so every caller
    # says the same thing.
    kind, message = classify_chat_error(UnreadableSecretError(), "openai_compatible")

    assert kind is ChatErrorKind.PROVIDER_AUTH
    assert "key" in message.casefold()


def test_transport_and_status_failures_are_unchanged() -> None:
    """The new branch sits beside the existing ones, not in front of them."""
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    unauthorized = httpx.HTTPStatusError(
        "401", request=request, response=httpx.Response(401, request=request)
    )

    assert classify_chat_error(unauthorized, "x")[0] is ChatErrorKind.PROVIDER_AUTH
    assert (
        classify_chat_error(httpx.ConnectError("down"), "llamacpp")[0]
        is ChatErrorKind.NETWORK
    )
    assert classify_chat_error(RuntimeError("?"), "x")[0] is ChatErrorKind.UNKNOWN


def _response_with_body(status: int, body: dict) -> httpx.Response:
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    return httpx.Response(status, request=request, json=body)


def test_a_prompt_too_long_for_the_window_names_the_real_problem() -> None:
    """llama.cpp's own error, told apart from an ordinary 400.

    Bucketed with every other status under PROVIDER_UNAVAILABLE, "try again
    shortly" tells someone to wait out a problem retrying will never fix: the
    prompt does not get shorter on its own.
    """
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = _response_with_body(
        400,
        {
            "error": {
                "code": 400,
                "type": "exceed_context_size_error",
                "message": "the request exceeds the available context size",
            }
        },
    )
    exc = httpx.HTTPStatusError("400", request=request, response=response)

    kind, message = classify_chat_error(exc, "llamacpp")

    assert kind is ChatErrorKind.CONTEXT_TOO_LONG
    assert "long" in message.casefold() or "context" in message.casefold()


def test_an_ordinary_400_is_still_provider_unavailable() -> None:
    """The new branch reads the body; a 400 with no llama.cpp shape falls
    through to the existing bucket rather than raising on a missing field."""
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = httpx.Response(400, request=request, content=b"not json")
    exc = httpx.HTTPStatusError("400", request=request, response=response)

    assert classify_chat_error(exc, "llamacpp")[0] is ChatErrorKind.PROVIDER_UNAVAILABLE
