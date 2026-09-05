import json

import pytest
from httpx import AsyncClient

from modules.llm import providers as registry
from modules.llm.providers.types import Message, Model

pytestmark = pytest.mark.integration


async def test_providers_report_health_and_capability(
    client: AsyncClient, ollama_server: str
) -> None:
    """The download UI is shown by capability, not by a provider's name."""
    body = (await client.get("/llm/providers")).json()

    ollama = next(entry for entry in body if entry["name"] == "ollama")
    assert ollama["healthy"] is True
    assert ollama["can_download"] is True


async def test_installed_models_carry_their_capabilities(
    client: AsyncClient, ollama_server: str
) -> None:
    """A chosen model has to be one the runtime actually holds."""
    body = (await client.get("/llm/providers/ollama/models")).json()

    assert {model["name"] for model in body} == {"qwen3:1.7b", "qwen3:4b"}
    assert "tools" in body[0]["capabilities"]


async def test_the_catalog_marks_what_is_installed(
    client: AsyncClient, ollama_server: str
) -> None:
    """The offer list greys what is already here."""
    body = (await client.get("/llm/providers/ollama/catalog")).json()

    entries = {entry["name"]: entry for entry in body}
    assert entries["qwen3:1.7b"]["installed"] is True
    assert entries["qwen3:32b"]["installed"] is False


async def test_an_unknown_provider_is_a_404(client: AsyncClient) -> None:
    """A path names a provider the registry does not have."""
    assert (await client.get("/llm/providers/openai/models")).status_code == 404


async def test_pull_streams_progress(client: AsyncClient, ollama_server: str) -> None:
    """The client needs progress, not one reply after minutes of silence."""
    steps = []
    async with client.stream(
        "POST", "/llm/providers/ollama/pull", json={"name": "qwen3:1.7b"}
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if line:
                steps.append(json.loads(line))

    assert steps[0]["status"] == "pulling manifest"
    assert steps[-1]["status"] == "success"


async def test_the_selection_is_read_after_it_is_set(client: AsyncClient) -> None:
    """Set persists the choice; read is how the rest of the app learns it."""
    assert (await client.get("/llm/selection/generation")).status_code == 404

    written = await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "qwen3:4b"},
    )
    assert written.status_code == 200
    assert written.json()["name"] == "qwen3:4b"

    read = await client.get("/llm/selection/generation")
    assert read.json() == written.json()


async def test_choosing_again_updates_in_place(client: AsyncClient) -> None:
    """One row per role: the second choice replaces the first, not adds to it."""
    await client.put(
        "/llm/selection/generation", json={"provider": "ollama", "name": "qwen3:1.7b"}
    )
    await client.put(
        "/llm/selection/generation", json={"provider": "ollama", "name": "qwen3:4b"}
    )

    assert (await client.get("/llm/selection/generation")).json()["name"] == "qwen3:4b"


async def test_a_selection_names_a_known_provider(client: AsyncClient) -> None:
    """A choice pointing at no provider would never resolve to a model."""
    reply = await client.put(
        "/llm/selection/generation", json={"provider": "openai", "name": "gpt-4o"}
    )
    assert reply.status_code == 422


async def test_a_chat_only_provider_hides_the_catalog(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remote API that cannot download offers no catalog to download from."""

    class Echo:
        name = "echo"

        async def health(self) -> bool:
            return True

        async def models(self) -> list[Model]:
            return []

        def chat(self, model: str, messages: list[Message]):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setitem(registry.REGISTRY, "echo", lambda: Echo())

    listed = (await client.get("/llm/providers")).json()
    echo = next(entry for entry in listed if entry["name"] == "echo")
    assert echo["can_download"] is False

    assert (await client.get("/llm/providers/echo/catalog")).status_code == 409
