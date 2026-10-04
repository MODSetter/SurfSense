"""Images in a chat request, and the request every other conversation still sends."""

import base64
import json

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Image, Message

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\nfake"
DONE = 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'


async def sent_body(messages: list[Message]) -> dict:
    """The JSON the endpoint received for one turn."""
    bodies: list[dict] = []

    def reply(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text=DONE)

    remote = OpenAICompatibleChatProvider(
        "http://remote/v1", transport=httpx.MockTransport(reply)
    )
    async for _ in remote.chat("m", messages):
        pass
    return bodies[0]


async def test_a_conversation_without_images_sends_todays_request() -> None:
    """String content, byte for byte, so no endpoint sees a change it never asked for."""
    body = await sent_body([Message("system", "rules"), Message("user", "hi")])

    assert body["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "hi"},
    ]


async def test_a_turn_with_images_sends_text_then_image_parts() -> None:
    """OpenAI's typed parts, which llama-server and every provider accept."""
    body = await sent_body(
        [Message("user", "what is this?", images=(Image("image/png", PNG),))]
    )

    encoded = base64.b64encode(PNG).decode()
    assert body["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is this?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                },
            ],
        }
    ]


async def test_only_the_turn_that_carries_images_changes_shape() -> None:
    """History without images stays string content beside an image turn."""
    body = await sent_body(
        [
            Message("user", "earlier"),
            Message("assistant", "reply"),
            Message("user", "now", images=(Image("image/png", PNG),)),
        ]
    )

    assert [type(m["content"]) for m in body["messages"]] == [str, str, list]
