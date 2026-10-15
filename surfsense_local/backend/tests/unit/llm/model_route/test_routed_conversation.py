"""A worker's conversation name crosses the model route with its request.

Studio names the calls that share a system prompt and sources, so an endpoint
that routes by the name sends them to the machine that cached their start. The
API runs the provider, so the name has to reach it.
"""

import json

import httpx
import pytest

from modules.llm.model_route.client import RoutedGenerator
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit


async def test_the_route_is_sent_the_conversation_a_studio_call_names() -> None:
    """Without it the key stops at the worker and no endpoint ever sees it."""
    bodies: list[dict] = []

    def answer(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200, text='data: {"type": "text", "text": "Hi"}\n\ndata: [DONE]\n\n'
        )

    routed = RoutedGenerator(
        "http://127.0.0.1:1", None, transport=httpx.MockTransport(answer)
    )

    reply = [
        text
        async for text in routed.chat(
            "qwen3", [Message("user", "hi")], conversation="surfsense-studio-ab12"
        )
    ]

    assert reply == ["Hi"]
    assert bodies[0]["conversation"] == "surfsense-studio-ab12"
