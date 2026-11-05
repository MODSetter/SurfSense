"""A Console refusal no retry can fix reaches the reader in the Console's own words.

The bodies are the Console's, as it answered live on 5 Nov 2026.
"""

import json

import httpx
import pytest

from modules.agent.agent_threads.error_kind import error_kind
from modules.agent.model_endpoint.console_refusal import refusal_for
from modules.chat.errors import ChatErrorKind, classify_chat_error
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

ZEN = "https://opencode.ai/inference/openai/v1"
ZEN_CHAT = f"{ZEN}/chat/completions"
NO_FUNDS = {
    "error": {
        "type": "server_error",
        "message": "Upstream request failed: Insufficient account funds",
    }
}
TRAINING = {
    "error": {
        "type": "server_error",
        "message": "Upstream request failed: This Go model trains on request data.",
    }
}
FREE_LIMIT = {
    "type": "error",
    "error": {
        "type": "FreeUsageLimitError",
        "message": "Free usage limit reached. Free models work in OpenCode.",
    },
}
FORBIDDEN = {"error": {"message": "This workspace cannot use this model."}}
BUSY = {"error": {"type": "rate_limit", "message": "Slow down"}}


async def _classified(
    status: int, body: dict, base_url: str = ZEN
) -> tuple[ChatErrorKind, str]:
    provider = OpenAICompatibleChatProvider(
        base_url,
        "oc_sk_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)),
    )
    with pytest.raises(httpx.HTTPStatusError) as refused:
        async for _ in provider.chat(
            "some-model", [Message(role="user", content="Hi")]
        ):
            pass
    return classify_chat_error(refused.value, "openai_compatible")


@pytest.mark.parametrize(
    ("status", "body", "words"),
    [
        (402, NO_FUNDS, "Insufficient account funds"),
        (400, TRAINING, "This Go model trains on request data."),
        (429, FREE_LIMIT, "Free usage limit reached. Free models work in OpenCode."),
        (403, FORBIDDEN, "This workspace cannot use this model."),
    ],
)
async def test_chat_shows_what_the_console_said(
    status: int, body: dict, words: str
) -> None:
    """Asking to try again would send the reader into a retry that cannot work."""
    assert await _classified(status, body) == (ChatErrorKind.PROVIDER_REFUSED, words)


async def test_a_real_rate_limit_still_asks_to_wait() -> None:
    """Waiting does fix this 429."""
    kind, _ = await _classified(429, BUSY)

    assert kind == ChatErrorKind.PROVIDER_RATE_LIMITED


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (402, ChatErrorKind.PROVIDER_UNAVAILABLE),
        (429, ChatErrorKind.PROVIDER_RATE_LIMITED),
    ],
)
async def test_another_servers_refusal_is_sorted_as_before(
    status: int, kind: ChatErrorKind
) -> None:
    """Only the Console's wording is known to name the fix."""
    classified, _ = await _classified(status, FREE_LIMIT, "https://api.openai.com/v1")

    assert classified == kind


def _relayed(status: int, body: dict) -> tuple[int, dict]:
    code, content = refusal_for(ZEN_CHAT)(status, json.dumps(body).encode())
    return code, json.loads(content)


@pytest.mark.parametrize(
    ("status", "sent", "words"),
    [
        (402, NO_FUNDS, "Insufficient account funds"),
        (429, FREE_LIMIT, "Free usage limit reached. Free models work in OpenCode."),
    ],
)
def test_the_agent_gets_the_same_kind_and_words(
    status: int, sent: dict, words: str
) -> None:
    """opencode hands its error's response body back, which keeps the relay's code."""
    relayed_status, body = _relayed(status, sent)

    assert relayed_status == status
    assert body["error"]["message"] == words
    assert error_kind({"response": {"body": json.dumps(body)}}) == "provider_refused"


def test_the_agent_can_still_wait_out_a_real_rate_limit() -> None:
    """Only a refusal no retry fixes carries the code."""
    _, body = _relayed(429, BUSY)

    assert "code" not in body["error"]


def test_the_agent_gets_a_reason_for_a_403_with_no_words() -> None:
    """A refusal with an empty body still has to say something."""
    status, content = refusal_for(ZEN_CHAT)(403, b"")
    body = json.loads(content)

    assert status == 403
    assert body["error"] == {
        "message": "the model answered 403",
        "code": "provider_refused",
    }


def test_the_agent_passes_on_another_hosts_403() -> None:
    """Every other model's words reach opencode untouched."""
    body = json.dumps(FORBIDDEN).encode()

    assert refusal_for("https://api.openai.com/v1/chat/completions")(403, body) == (
        403,
        body,
    )


def _status_error(url: str, status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    return httpx.HTTPStatusError(
        "refused", request=request, response=httpx.Response(status, request=request)
    )


@pytest.mark.parametrize(
    ("url", "status"),
    [(ZEN_CHAT, 401), ("https://api.openai.com/v1/chat/completions", 403)],
)
def test_chat_still_blames_the_key_elsewhere(url: str, status: int) -> None:
    """A wrong Console key, or another server's 403, is still the key."""
    kind, _ = classify_chat_error(_status_error(url, status), "openai_compatible")

    assert kind == ChatErrorKind.PROVIDER_AUTH


def _unread_failure(url: str, status: int) -> httpx.HTTPStatusError:
    """A failure raised mid-stream, as a `response.failed` event raises one."""
    request = httpx.Request("POST", url)
    response = httpx.Response(status, request=request, stream=httpx.ByteStream(b"{}"))
    return httpx.HTTPStatusError("It failed", request=request, response=response)


def test_a_failure_whose_body_was_never_read_is_still_sorted() -> None:
    """Sorting an error must not raise one of its own, on any provider."""
    failure = _unread_failure("https://chatgpt.com/backend-api/codex/responses", 200)

    kind, _ = classify_chat_error(failure, "openai_compatible")

    assert kind == ChatErrorKind.PROVIDER_UNAVAILABLE


def test_a_console_refusal_with_an_unread_body_keeps_its_words() -> None:
    """The status and the host decide; only the free limit needs the body."""
    kind, words = classify_chat_error(
        _unread_failure(ZEN_CHAT, 402), "openai_compatible"
    )

    assert (kind, words) == (ChatErrorKind.PROVIDER_REFUSED, "It failed")
