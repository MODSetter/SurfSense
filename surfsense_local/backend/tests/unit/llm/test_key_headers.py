import httpx
import pytest

from modules.llm.connections import service
from modules.llm.connections.service import probe_connection
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider

pytestmark = pytest.mark.unit
LISTING = {"data": [{"id": "claude-sonnet-5", "type": "model"}]}


def _recording(seen: list[httpx.Request]) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=LISTING)

    return httpx.MockTransport(answer)


async def test_anthropic_is_listed_with_its_own_key_headers() -> None:
    """Anthropic's model listing reads x-api-key, not a bearer token."""
    seen: list[httpx.Request] = []
    provider = OpenAICompatibleChatProvider(
        "https://api.anthropic.com/v1", "sk-ant-test", transport=_recording(seen)
    )

    models = await provider.models()

    assert [model.name for model in models] == ["claude-sonnet-5"]
    assert seen[0].url == "https://api.anthropic.com/v1/models"
    assert seen[0].headers["x-api-key"] == "sk-ant-test"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in seen[0].headers


async def test_another_server_keeps_the_bearer_token() -> None:
    """Every other OpenAI-compatible server is reached as before."""
    seen: list[httpx.Request] = []
    provider = OpenAICompatibleChatProvider(
        "https://api.openai.com/v1", "sk-test", transport=_recording(seen)
    )

    await provider.models()

    assert seen[0].headers["authorization"] == "Bearer sk-test"
    assert "x-api-key" not in seen[0].headers


async def test_discovering_anthropic_sends_its_own_key_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connecting runs discovery before any provider exists."""
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def client(**kwargs: object) -> httpx.AsyncClient:
        return real_client(**kwargs, transport=_recording(seen))

    monkeypatch.setattr(service.httpx, "AsyncClient", client)

    discovered = await probe_connection("https://api.anthropic.com/v1", "sk-ant-test")

    assert [model.name for model in discovered] == ["claude-sonnet-5"]
    assert seen[0].headers["x-api-key"] == "sk-ant-test"
    assert "authorization" not in seen[0].headers
