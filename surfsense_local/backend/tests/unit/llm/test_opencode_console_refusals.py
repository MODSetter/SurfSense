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
