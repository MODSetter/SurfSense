"""A conversation's requests reach the machine that cached its prompt.

A provider caches a prompt where it read it. OpenRouter keeps a conversation on
one provider by `session_id` and caches Claude only behind `cache_control`;
OpenAI routes by `prompt_cache_key`. Any other endpoint gets neither, because a
strict one rejects a field it does not know.
"""

import json

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit
CACHE_FIELDS = {"session_id", "prompt_cache_key", "cache_control"}


async def _sent(base_url: str, model: str, conversation: str | None) -> dict:
    """The body one streamed turn sends to this endpoint."""
    bodies: list[dict] = []

    def answer(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n',
        )

    provider = OpenAICompatibleChatProvider(
        base_url, "key", transport=httpx.MockTransport(answer)
    )
    async for _ in provider.chat_deltas(
        model, [Message("user", "hi")], conversation=conversation
    ):
        pass
    return bodies[-1]


async def test_openrouter_keeps_a_conversation_on_one_provider_and_caches_claude() -> (
    None
):
    """Sticky routing for every model; Claude also needs the marker to cache at all."""
    claude = await _sent(
        "https://openrouter.ai/api/v1", "anthropic/claude-sonnet-5.5", "thread-7"
    )
    gpt = await _sent("https://openrouter.ai/api/v1", "openai/gpt-5.5", "thread-7")

    assert claude["session_id"] == "thread-7"
    assert claude["cache_control"] == {"type": "ephemeral"}
    assert gpt["session_id"] == "thread-7"
    assert "cache_control" not in gpt


async def test_openai_routes_a_conversation_by_its_cache_key() -> None:
    """Requests sharing a key go to the machine likeliest to hold their prefix."""
    sent = await _sent("https://api.openai.com/v1", "gpt-5.5", "thread-7")

    assert sent["prompt_cache_key"] == "thread-7"


async def test_any_other_endpoint_or_no_conversation_gets_no_cache_field() -> None:
    """A strict endpoint answers 422 to a field it does not know."""
    mistral = await _sent("https://api.mistral.ai/v1", "mistral-large", "thread-7")
    unnamed = await _sent("https://openrouter.ai/api/v1", "openai/gpt-5.5", None)

    assert not CACHE_FIELDS & mistral.keys()
    assert not CACHE_FIELDS & unnamed.keys()
