"""OpenCode Go requires a session id, and asks every client to name itself.

https://opencode.ai/docs/go https://opencode.ai/v2/docs/console/harnesses
"""

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit
GO = "https://opencode.ai/inference/go/openai/v1"
REPLY = 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'


async def _sent(base_url: str, conversation: str | None) -> httpx.Headers:
    """The headers one streamed turn sends to this endpoint."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=REPLY)

    provider = OpenAICompatibleChatProvider(
        base_url, "oc_sk_test", transport=httpx.MockTransport(answer)
    )
    async for _ in provider.chat(
        "glm-5.3", [Message(role="user", content="Hi")], conversation=conversation
    ):
        pass
    return seen[0].headers


async def test_a_conversation_keeps_one_session_id() -> None:
    """The docs ask for a stable id, so the prefix is added the same way each time."""
    first = await _sent(GO, "thread-42")
    second = await _sent(GO, "thread-42")

    assert first["x-opencode-session"] == "ses_thread-42"
    assert second["x-opencode-session"] == first["x-opencode-session"]


async def test_an_id_already_in_the_documented_shape_is_kept() -> None:
    """opencode's own session ids start with ses_."""
    headers = await _sent(GO, "ses_42")

    assert headers["x-opencode-session"] == "ses_42"


async def test_a_request_with_no_conversation_still_sends_a_session_id() -> None:
    """A title or a connection check has none, and Go requires one on every request."""
    first = await _sent(GO, None)
    second = await _sent(GO, None)

    assert first["x-opencode-session"].startswith("ses_")
    assert first["x-opencode-session"] != second["x-opencode-session"]


async def test_the_console_is_told_who_is_calling() -> None:
    """The docs ask each client to identify itself with its own user agent."""
    headers = await _sent("https://opencode.ai/inference/openai/v1", "thread-42")

    assert headers["user-agent"] == "SurfSense"


async def test_another_server_gets_neither() -> None:
    """Only OpenCode's docs ask for these."""
    headers = await _sent("https://api.openai.com/v1", "thread-42")

    assert "x-opencode-session" not in headers
    assert headers["user-agent"] != "SurfSense"
