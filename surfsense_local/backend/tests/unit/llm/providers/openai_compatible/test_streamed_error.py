"""An error an endpoint sends inside its stream fails the reply.

Once tokens have gone out the status is already 200, so llama.cpp and OpenRouter
report a later failure as a `data:` chunk carrying `error`. Read as an empty
delta, a reply cut off by it was stored and shown as if it had finished.
"""

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import (
    OpenAICompatibleChatProvider,
    StreamedError,
)
from modules.llm.providers.types import Delta, Message

pytestmark = pytest.mark.unit

# The shapes each endpoint documents or sends, after some answer text.
LLAMACPP = '{"error":{"code":500,"message":"decode failed","type":"server_error"}}'
OPENROUTER = (
    '{"id":"gen-1","object":"chat.completion.chunk",'
    '"error":{"code":"server_error","message":"decode failed"},'
    '"choices":[{"index":0,"delta":{"content":""},"finish_reason":"error"}]}'
)


def endpoint(*chunks: str) -> OpenAICompatibleChatProvider:
    """A 200 stream of these chunks, as an endpoint past its first token sends."""
    body = "".join(f"data: {chunk}\n\n" for chunk in chunks)
    return OpenAICompatibleChatProvider(
        "http://endpoint/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
    )


@pytest.mark.parametrize(
    "error", [LLAMACPP, OPENROUTER], ids=["llamacpp", "openrouter"]
)
async def test_an_error_after_text_fails_the_reply_with_its_message(error: str) -> None:
    """The text before the error still arrives; the stream then fails, not ends."""
    provider = endpoint('{"choices":[{"delta":{"content":"Revenue"}}]}', error)
    received: list[Delta] = []

    with pytest.raises(StreamedError, match="decode failed"):
        async for delta in provider.chat_deltas("m", [Message("user", "hi")]):
            received.append(delta)

    assert received == [Delta("Revenue")]


async def test_an_error_sent_as_a_string_still_fails_the_reply() -> None:
    """Not every endpoint nests a message, and a bare error is still a failure."""
    provider = endpoint('{"error":"overloaded"}')

    with pytest.raises(StreamedError, match="overloaded"):
        async for _ in provider.chat("m", [Message("user", "hi")]):
            pass
