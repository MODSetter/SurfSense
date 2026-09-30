"""Whether the selected chat model reads images, as the composer learns it."""

import pytest
from httpx import AsyncClient

from . import conftest

pytestmark = pytest.mark.integration


async def _connect(client: AsyncClient, base_url: str, **fields: str) -> dict:
    reply = await client.post(
        "/llm/connections",
        json={
            "label": "Gateway",
            "provider": "openai_compatible",
            "base_url": base_url,
            **fields,
        },
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


async def test_a_local_model_answers_as_llama_cpp_lists_it(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """The router's own `/models` answer, with no load and no stored copy."""
    conftest.SEES.add("Qwen3-4B-Q4_K_M")

    seeing = await client.put(
        "/llm/selection/text_gen",
        json={"provider": "llamacpp", "name": "Qwen3-4B-Q4_K_M"},
    )
    assert seeing.json()["reads_images"] is True
    assert (await client.get("/llm/selection/text_gen")).json()["reads_images"] is True

    blind = await client.put(
        "/llm/selection/text_gen",
        json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"},
    )
    assert blind.json()["reads_images"] is False


async def test_a_remote_model_answers_from_the_manifest(
    client: AsyncClient, openai_server: str
) -> None:
    """The catalog provider's entry, through the connection the selection names."""
    connection = await _connect(client, openai_server)

    chosen = await client.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "anthropic/claude-3.5-sonnet",
        },
    )

    assert chosen.json()["reads_images"] is True


async def test_the_model_list_badges_what_the_selection_will_say(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint declares these models' types, which skips the manifest for
    them; the badge still reads it, so the list never disagrees with attach."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [*conftest.REMOTE_MODELS, {"id": "gpt-3.5-turbo"}]
    )
    connection = await _connect(client, openai_server, catalog_provider="openai")

    listed = {
        m["name"]: m["reads_images"]
        for m in (
            await client.get(f"/llm/connections/{connection['id']}/models")
        ).json()
    }

    assert listed == {
        "anthropic/claude-3.5-sonnet": True,
        "black-forest-labs/flux": False,
        "gpt-3.5-turbo": False,
    }


async def test_an_unusable_model_carries_no_vision_chip(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """agentrouter serves claude-opus-5, which reads images, only through
    Anthropic's protocol: a row that fills no slot must not promise vision."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [*conftest.REMOTE_MODELS, {"id": "claude-opus-5"}]
    )
    connection = await _connect(client, openai_server, catalog_provider="agentrouter")

    listed = {
        m["name"]: m
        for m in (
            await client.get(f"/llm/connections/{connection['id']}/models")
        ).json()
    }

    assert listed["claude-opus-5"]["unusable_reason"]
    assert listed["claude-opus-5"]["reads_images"] is False
