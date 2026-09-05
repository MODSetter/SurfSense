import pytest
from httpx import AsyncClient

from modules.llm.providers.openrouter.provider import OpenRouterProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.integration


async def _openrouter_entry(client: AsyncClient) -> dict:
    body = (await client.get("/llm/providers")).json()
    return next(entry for entry in body if entry["name"] == "openrouter")


async def test_without_a_key_openrouter_is_unconfigured(client: AsyncClient) -> None:
    """A BYO-key provider announces it needs a key, and reports unhealthy."""
    entry = await _openrouter_entry(client)

    assert entry["requires_key"] is True
    assert entry["configured"] is False
    assert entry["healthy"] is False
    assert entry["can_download"] is False


async def test_setting_a_key_makes_it_healthy(
    client: AsyncClient, openrouter_server: str
) -> None:
    """The key set by the client is what lets the provider answer."""
    written = await client.put(
        "/llm/providers/openrouter/credentials", json={"api_key": "sk-test"}
    )
    assert written.status_code == 200
    assert written.json() == {"provider": "openrouter", "configured": True}

    entry = await _openrouter_entry(client)
    assert entry["configured"] is True
    assert entry["healthy"] is True


async def test_the_key_is_never_returned(
    client: AsyncClient, openrouter_server: str
) -> None:
    """Only the presence of a key is exposed, never the secret itself."""
    await client.put(
        "/llm/providers/openrouter/credentials", json={"api_key": "sk-secret"}
    )
    dumped = (await client.get("/llm/providers")).text
    assert "sk-secret" not in dumped


async def test_only_chat_models_are_listed(
    client: AsyncClient, openrouter_server: str
) -> None:
    """A text model can answer; an image model is not offered for generation."""
    await client.put(
        "/llm/providers/openrouter/credentials", json={"api_key": "sk-test"}
    )
    body = (await client.get("/llm/providers/openrouter/models")).json()

    assert {model["name"] for model in body} == {"anthropic/claude-3.5-sonnet"}
    assert body[0]["capabilities"] == ["completion"]


async def test_without_a_key_no_models_are_listed(client: AsyncClient) -> None:
    """No key means nothing to answer with, not an error."""
    assert (await client.get("/llm/providers/openrouter/models")).json() == []


async def test_a_key_only_makes_sense_where_one_is_needed(client: AsyncClient) -> None:
    """Ollama holds its own models; it has no key to set."""
    reply = await client.put(
        "/llm/providers/ollama/credentials", json={"api_key": "sk-test"}
    )
    assert reply.status_code == 409


async def test_an_empty_key_is_rejected(client: AsyncClient) -> None:
    """A blank key would leave the provider unconfigured while looking set."""
    reply = await client.put(
        "/llm/providers/openrouter/credentials", json={"api_key": "  "}
    )
    assert reply.status_code == 422


async def test_clearing_a_key_unconfigures_the_provider(
    client: AsyncClient, openrouter_server: str
) -> None:
    """Removing the key returns the provider to its unconfigured state."""
    await client.put(
        "/llm/providers/openrouter/credentials", json={"api_key": "sk-test"}
    )
    assert (
        await client.delete("/llm/providers/openrouter/credentials")
    ).status_code == 204

    assert (await _openrouter_entry(client))["configured"] is False


async def test_chat_streams_token_deltas(openrouter_server: str) -> None:
    """The provider yields each token as the OpenAI SSE frames arrive."""
    provider = OpenRouterProvider(openrouter_server, api_key="sk-test")
    messages = [Message(role="user", content="hi")]

    deltas = [
        delta async for delta in provider.chat("anthropic/claude-3.5-sonnet", messages)
    ]

    assert "".join(deltas) == "Hello"
