"""Asking for JSON and getting JSON.

48 of the 69 prompt files demand a JSON object. `response_format` masks every
token that would produce invalid JSON, so a malformed answer stops being
something to repair and becomes something that cannot be emitted.
"""

import httpx
import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.types import Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


def provider_for(fake: FakeRouter) -> LlamaCppProvider:
    """A provider wired to a fake router rather than a live sidecar."""
    return LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())


async def drain(stream) -> str:
    """Collect a streamed reply into one string."""
    return "".join([chunk async for chunk in stream])


@pytest.mark.asyncio
async def test_a_plain_turn_asks_for_no_particular_shape() -> None:
    """Chat is prose, and constraining it would be a mistake."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")

    await drain(provider_for(fake).chat("m", [Message("user", "hi")]))

    assert "response_format" not in fake.chat_bodies[-1]


@pytest.mark.asyncio
async def test_a_schema_is_sent_as_a_response_format() -> None:
    """The schema reaches the runtime in the shape the OpenAI API defines."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")

    await drain(
        provider_for(fake).chat("m", [Message("user", "hi")], json_schema=SCHEMA)
    )

    body = fake.chat_bodies[-1]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA


@pytest.mark.asyncio
async def test_a_template_that_refuses_a_schema_still_answers() -> None:
    """llama.cpp issue #29006: json_schema on the chat endpoint returns 400 for
    some templates. Studio would lose a whole format over a template quirk, so
    the request is retried unconstrained and the parser's repair path catches
    what the mask would have prevented.
    """
    fake = FakeRouter(["m"])
    fake.loaded.add("m")
    fake.reject_response_format = True

    text = await drain(
        provider_for(fake).chat("m", [Message("user", "hi")], json_schema=SCHEMA)
    )

    assert text == "Hello"
    assert "response_format" not in fake.chat_bodies[-1]
    assert len(fake.chat_bodies) == 2


@pytest.mark.asyncio
async def test_an_unrelated_failure_is_not_swallowed_by_the_fallback() -> None:
    """Only a schema rejection is worth retrying. Retrying everything would turn
    a broken runtime into a silently worse answer."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")
    fake.fail_chat_with = 503

    with pytest.raises(httpx.HTTPStatusError):
        await drain(
            provider_for(fake).chat("m", [Message("user", "hi")], json_schema=SCHEMA)
        )
