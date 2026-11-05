"""OpenCode's Console lists its models apart from where they answer.

The docs give `/inference/v1/models` and `/inference/go/v1/models`, while
`/inference/openai/v1/models` is a 404.
https://opencode.ai/docs/zen https://opencode.ai/docs/go
"""

import httpx
import pytest

from modules.llm.connections import service
from modules.llm.connections.service import probe_connection
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider

pytestmark = pytest.mark.unit
LISTING = {"data": [{"id": "claude-opus-5-5", "type": "chat"}]}
PLANS = [
    (
        "https://opencode.ai/inference/openai/v1",
        "https://opencode.ai/inference/v1/models",
    ),
    (
        "https://opencode.ai/inference/go/openai/v1",
        "https://opencode.ai/inference/go/v1/models",
    ),
]


def _recording(seen: list[httpx.Request]) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=LISTING)

    return httpx.MockTransport(answer)


@pytest.mark.parametrize(("base_url", "listing"), PLANS)
async def test_the_chat_provider_lists_where_the_docs_say(
    base_url: str, listing: str
) -> None:
    """Chat's model checks read the same list as connecting."""
    seen: list[httpx.Request] = []
    provider = OpenAICompatibleChatProvider(
        base_url, "oc_sk_test", transport=_recording(seen)
    )

    models = await provider.models()

    assert [model.name for model in models] == ["claude-opus-5-5"]
    assert str(seen[0].url) == listing


@pytest.mark.parametrize(("base_url", "listing"), PLANS)
async def test_connecting_lists_where_the_docs_say(
    base_url: str, listing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connecting runs discovery before any provider exists."""
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def client(**kwargs: object) -> httpx.AsyncClient:
        return real_client(**kwargs, transport=_recording(seen))

    monkeypatch.setattr(service.httpx, "AsyncClient", client)

    await probe_connection(base_url, "oc_sk_test")

    assert str(seen[0].url) == listing


async def test_another_server_lists_under_its_base_url() -> None:
    """The same path on another host says nothing about OpenCode."""
    seen: list[httpx.Request] = []
    provider = OpenAICompatibleChatProvider(
        "https://example.test/inference/openai/v1", "key", transport=_recording(seen)
    )

    await provider.models()

    assert str(seen[0].url) == "https://example.test/inference/openai/v1/models"
