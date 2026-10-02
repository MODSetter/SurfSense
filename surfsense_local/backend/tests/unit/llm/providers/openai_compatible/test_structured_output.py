"""A schema an endpoint refuses costs one unconstrained retry, not the reply.

Every Studio JSON format sends one, to a local model and to any connection, and
not every OpenAI-compatible endpoint accepts `response_format: json_schema`.
"""

import json

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}}
ANSWER = 'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n'


class Endpoint:
    """An endpoint that refuses a schema with `refuse`, and records each body."""

    def __init__(self, refuse: int | None = 400, status: int = 200) -> None:
        self.refuse = refuse
        self.status = status
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        if "response_format" in body and self.refuse is not None:
            return httpx.Response(
                self.refuse, json={"error": {"message": "unsupported"}}
            )
        return httpx.Response(self.status, text=ANSWER)


async def ask(endpoint: Endpoint, schema: dict | None = SCHEMA) -> str:
    """The whole answer to one question sent with `schema`."""
    provider = OpenAICompatibleChatProvider(
        "http://remote/v1", transport=httpx.MockTransport(endpoint)
    )
    return "".join(
        [
            d
            async for d in provider.chat(
                "m", [Message("user", "hi")], json_schema=schema
            )
        ]
    )


async def test_an_endpoint_that_refuses_a_schema_is_asked_again_without_one() -> None:
    """The parser reads an unconstrained reply as it always did."""
    endpoint = Endpoint(refuse=400)

    assert await ask(endpoint) == "Hello"
    assert len(endpoint.bodies) == 2
    assert "response_format" in endpoint.bodies[0]
    assert "response_format" not in endpoint.bodies[1]


async def test_a_refusal_unrelated_to_a_schema_is_not_retried() -> None:
    """Retrying a broken endpoint would only hide it behind a second failure."""
    endpoint = Endpoint(refuse=503)

    with pytest.raises(httpx.HTTPStatusError):
        await ask(endpoint)
    assert len(endpoint.bodies) == 1


async def test_a_bad_request_without_a_schema_is_not_retried() -> None:
    """Without a schema there is nothing to drop, so a 400 is the answer."""
    endpoint = Endpoint(refuse=None, status=400)

    with pytest.raises(httpx.HTTPStatusError):
        await ask(endpoint, schema=None)
    assert len(endpoint.bodies) == 1
