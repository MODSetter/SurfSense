"""A remote text model answers on the route its provider's manifest entry records.

Sakana serves `fugu` only on /responses; every model the manifest does not mark
so, and every model of a custom connection, answers on /chat/completions.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.providers.types import Message
from modules.llm.resolution import resolve_generation
from shared.db import create_session_factory

from . import conftest
from .conftest import REMOTE_REQUESTS

pytestmark = pytest.mark.integration


async def _choose(
    client: AsyncClient, base_url: str, catalog_provider: str, name: str
) -> None:
    connection = (
        await client.post(
            "/llm/connections",
            json={
                "label": catalog_provider,
                "provider": "openai_compatible",
                "base_url": base_url,
                "api_key": "secret",
                "catalog_provider": catalog_provider,
            },
        )
    ).json()
    chosen = await client.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": name,
        },
    )
    assert chosen.status_code == 200, chosen.text


async def _answer(engine: Engine, name: str) -> str:
    with create_session_factory(engine)() as session:
        resolved = resolve_generation(session)
    return "".join(
        [c async for c in resolved.generator.chat(name, [Message("user", "hi")])]
    )


async def test_a_responses_model_answers_on_responses_with_its_key(
    client: AsyncClient,
    engine: Engine,
    openai_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chat, titles and Studio reach it there, under the connection's own key."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [{"id": "fugu"}, *conftest.REMOTE_MODELS]
    )
    await _choose(client, openai_server, "sakana", "fugu")
    REMOTE_REQUESTS.clear()

    assert await _answer(engine, "fugu") == "Hello"
    assert [path for path, _ in REMOTE_REQUESTS] == ["/responses"]


@pytest.mark.parametrize("catalog_provider", ["openai", "custom"])
async def test_every_other_model_answers_on_chat_completions(
    client: AsyncClient,
    engine: Engine,
    openai_server: str,
    monkeypatch: pytest.MonkeyPatch,
    catalog_provider: str,
) -> None:
    """OpenAI's own models, and a custom endpoint's `fugu`, are unchanged."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [{"id": "fugu"}, *conftest.REMOTE_MODELS]
    )
    await _choose(client, openai_server, catalog_provider, "fugu")
    REMOTE_REQUESTS.clear()

    assert await _answer(engine, "fugu") == "Hello"
    assert [path for path, _ in REMOTE_REQUESTS] == ["/chat/completions"]
