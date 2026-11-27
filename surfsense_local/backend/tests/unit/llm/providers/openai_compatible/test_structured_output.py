"""An endpoint that refuses a JSON schema still answers.

DeepSeek's API refuses a `json_schema` request with a 400, "This response_format
type is unavailable now", and llama.cpp does for some templates (issue #29006).
Every Studio format that asks for JSON sends a schema, so without a fallback
such a connection fails all of them, though its model is fine.
"""

import json

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}
ANSWER = 'data: {"choices":[{"delta":{"content":"{\\"title\\": \\"T\\"}"}}]}\n\n'
REFUSAL = {"error": {"message": "This response_format type is unavailable now"}}


class Endpoint:
    """Records each request body and answers it with the next status in turn."""

    def __init__(self, *statuses: int) -> None:
        self.statuses = list(statuses)
        self.bodies: list[dict] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        status = self.statuses.pop(0)
        if status == 200:
            return httpx.Response(200, text=ANSWER)
        return httpx.Response(status, json=REFUSAL)

    def provider(self) -> OpenAICompatibleChatProvider:
        return OpenAICompatibleChatProvider(
            "https://api.example.com/v1",
            "key",
            transport=httpx.MockTransport(self.handle),
        )


async def ask(endpoint: Endpoint, schema: dict | None = SCHEMA) -> str:
    """One Studio-shaped request, collected into the reply text."""
    stream = endpoint.provider().chat(
        "m",
        [Message("user", "hi")],
        max_tokens=64,
        temperature=0.2,
        json_schema=schema,
    )
    return "".join([chunk async for chunk in stream])


async def test_a_schema_the_endpoint_refuses_is_asked_again_without_it() -> None:
    """The same request once more, less the schema, and its answer is the reply."""
    endpoint = Endpoint(400, 200)

    assert await ask(endpoint) == '{"title": "T"}'

    first, retry = endpoint.bodies
    assert first["response_format"]["json_schema"]["schema"] == SCHEMA
    assert "response_format" not in retry
    assert {k: v for k, v in first.items() if k != "response_format"} == retry


async def test_an_endpoint_that_takes_the_schema_is_asked_once() -> None:
    """The fallback costs nothing where the schema is taken."""
    endpoint = Endpoint(200)

    assert await ask(endpoint) == '{"title": "T"}'

    assert len(endpoint.bodies) == 1
    assert "response_format" in endpoint.bodies[0]


async def test_a_400_without_a_schema_is_not_retried() -> None:
    """Nothing was asked that could be dropped, so the refusal stands."""
    endpoint = Endpoint(400)

    with pytest.raises(httpx.HTTPStatusError, match="unavailable now"):
        await ask(endpoint, schema=None)

    assert len(endpoint.bodies) == 1


async def test_a_failure_other_than_a_400_is_not_retried() -> None:
    """Only a refusal of the request can be answered by changing it; retrying an
    outage would hide it behind a worse answer."""
    endpoint = Endpoint(503)

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await ask(endpoint)

    assert raised.value.response.status_code == 503
    assert len(endpoint.bodies) == 1


async def test_a_400_the_unconstrained_request_also_gets_fails_once() -> None:
    """A refusal that was never about the schema is reported, after one retry."""
    endpoint = Endpoint(400, 400)

    with pytest.raises(httpx.HTTPStatusError, match="unavailable now"):
        await ask(endpoint)

    assert len(endpoint.bodies) == 2
