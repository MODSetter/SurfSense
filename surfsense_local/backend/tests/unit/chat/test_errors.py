"""Sorting a failed generation into something the user can act on."""

import json

import httpx
import pytest

from modules.chat.errors import ChatErrorKind, classify_chat_error
from modules.llm.providers.openai_compatible.chat import (
    OpenAICompatibleChatProvider,
    StreamedError,
)
from modules.llm.providers.openai_responses import PlanLimitError, SignInRequiredError
from modules.llm.providers.types import Message
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


def test_a_model_the_local_runtime_cannot_load_says_so() -> None:
    """The failure the search gate used to prevent before the download.

    llama-server answers 500 when a model fails to load: an architecture this
    build has no builder for, or one it builds and then aborts on. Bucketed
    under PROVIDER_UNAVAILABLE that reads "try again shortly", which sends
    someone into a retry loop over something that can never work. There is no
    remote provider here either. It is our own subprocess.
    """
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = _response_with_body(
        500,
        {
            "error": {
                "code": 500,
                "type": "server_error",
                "message": "model name=GLM-5.3-Flash-Q4_K_M failed to load",
            }
        },
    )
    exc = httpx.HTTPStatusError("500", request=request, response=response)

    kind, message = classify_chat_error(exc, "llamacpp")

    assert kind is ChatErrorKind.MODEL_CANNOT_RUN
    assert "try again" not in message.casefold()
    assert "—" not in message
    assert "-" not in message


def test_a_remote_provider_500_is_still_temporary() -> None:
    """A hosted endpoint answering 500 really can recover on a retry. Only the
    local runtime is making a statement about the file on disk."""
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = httpx.Response(500, request=request, content=b"")
    exc = httpx.HTTPStatusError("500", request=request, response=response)

    assert classify_chat_error(exc, "openai")[0] is ChatErrorKind.PROVIDER_UNAVAILABLE


def test_a_chatgpt_account_that_must_sign_in_again_says_so() -> None:
    """Not `provider_auth`, whose fix is a new key a ChatGPT connection never has."""
    kind, message = classify_chat_error(SignInRequiredError(), "openai_compatible")

    assert kind is ChatErrorKind.SUBSCRIPTION_SIGN_IN
    assert "sign in" in message.casefold()


def test_a_reached_plan_limit_is_not_a_moment_to_retry() -> None:
    """Not `provider_rate_limited`, whose text says to try again in a moment."""
    kind, message = classify_chat_error(PlanLimitError("Limit."), "openai_compatible")

    assert kind is ChatErrorKind.SUBSCRIPTION_LIMIT
    assert "limit" in message.casefold()


@pytest.mark.parametrize(
    "said",
    [
        "Context size has been exceeded.",
        "failed to find free space in the KV cache",
        "failed to find a memory slot for batch of size 512",
    ],
)
def test_a_shared_cache_that_ran_out_of_room_says_so(said: str) -> None:
    """With several replies sharing one cache, llama.cpp ends every request in
    an overflow. Admission makes it rare; when it happens it is not a model
    that cannot run, and a retry with fewer replies running will work."""
    request = httpx.Request("POST", "http://x/v1/chat/completions")
    response = _response_with_body(
        500, {"error": {"code": 500, "type": "server_error", "message": said}}
    )
    exc = httpx.HTTPStatusError("500", request=request, response=response)

    kind, message = classify_chat_error(exc, "llamacpp")

    assert kind is ChatErrorKind.RUNTIME_BUSY
    assert "running together" in message


async def _streamed_failure(said: str) -> StreamedError:
    """What the chat provider raises when llama.cpp fails a reply it began."""
    chunks = (
        {"choices": [{"delta": {"content": "Revenue"}}]},
        {"error": {"code": 500, "message": said, "type": "server_error"}},
    )
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    provider = OpenAICompatibleChatProvider(
        "http://x/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
    )
    with pytest.raises(StreamedError) as raised:
        async for _ in provider.chat("m", [Message("user", "hi")]):
            pass
    return raised.value


async def test_a_shared_cache_overflow_mid_reply_says_so() -> None:
    """Past the first token llama.cpp sends the overflow to every running reply
    as an error chunk rather than a 500. It is the same overflow, and the same
    retry with fewer replies running works."""
    exc = await _streamed_failure("Context size has been exceeded.")

    kind, message = classify_chat_error(exc, "llamacpp")

    assert kind is ChatErrorKind.RUNTIME_BUSY
    assert "running together" in message


async def test_other_mid_reply_failures_stay_unknown() -> None:
    """Only the local runtime's overflow names a fix; a hosted endpoint's
    words, or another local failure, are not read as one."""
    overflow = await _streamed_failure("Context size has been exceeded.")
    compute = await _streamed_failure("Compute error.")

    assert classify_chat_error(overflow, "openai_compatible")[0] is (
        ChatErrorKind.UNKNOWN
    )
    assert classify_chat_error(compute, "llamacpp")[0] is ChatErrorKind.UNKNOWN


def test_a_claude_plan_that_must_sign_in_again_points_at_claude_code() -> None:
    """Its sign-in is Claude Code's, in a terminal, not ChatGPT's in Model setup."""
    from modules.llm.subscriptions.claude.errors import ClaudeSignInRequiredError

    kind, message = classify_chat_error(
        ClaudeSignInRequiredError("signed out"), "openai_compatible"
    )

    assert kind is ChatErrorKind.CLAUDE_SIGN_IN
    assert "Claude Code" in message
    assert "ChatGPT" not in message


def test_a_used_up_claude_plan_says_whose_limit_it_is() -> None:
    """The limit is the Claude plan's, which resets on its own."""
    from modules.llm.subscriptions.claude.errors import ClaudePlanLimitError

    kind, message = classify_chat_error(
        ClaudePlanLimitError("limit"), "openai_compatible"
    )

    assert kind is ChatErrorKind.CLAUDE_LIMIT
    assert "Claude" in message
    assert "ChatGPT" not in message


def test_a_host_turned_off_during_a_reply_says_where_to_allow_it() -> None:
    """Not `unknown`: the fix is a switch in Settings, which the user can flip."""
    from modules.egress.service import EgressDeniedError

    kind, message = classify_chat_error(
        EgressDeniedError("host:api.anthropic.com"), "openai_compatible"
    )

    assert kind is ChatErrorKind.EGRESS_DISABLED
    assert "Settings > Network" in message
