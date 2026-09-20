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
