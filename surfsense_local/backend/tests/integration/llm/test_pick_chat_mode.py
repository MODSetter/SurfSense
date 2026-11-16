"""Picking Basic (Q&A) or Agentic in the composer saves it as the model's default at once."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import llamacpp
from shared.config import get_agent_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

OPENROUTER = "https://openrouter.ai/api/v1"
OPENAI = "https://api.openai.com/v1"


@pytest.fixture(autouse=True)
def opencode_staged(monkeypatch: pytest.MonkeyPatch) -> None:
    """As an installer ships: opencode beside the API, no developer switch."""
    settings = get_agent_settings()
    monkeypatch.setattr(settings, "opencode_url", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "opencode_password", "not-a-running-opencode")
    monkeypatch.setattr(settings, "agent_untested_models", False)


def _select(engine: Engine, name: str, catalog_provider: str, base_url: str) -> dict:
    """A remote selection written as the selection route leaves it; nothing is sent to the host.

    Returns the model as a pick names it.
    """
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label=f"Remote {name}",
            provider="openai_compatible",
            base_url=base_url,
            catalog_provider=catalog_provider,
        )
        session.add(connection)
        session.flush()
        session.merge(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name=name,
            )
        )
        session.commit()
        return {
            "provider": "openai_compatible",
            "connection_id": connection.id,
            "name": name,
        }


async def _modes(client: AsyncClient) -> dict:
    reply = await client.get("/llm/selection/text_gen")
    assert reply.status_code == 200, reply.text
    return reply.json()["capability"]["modes"]


async def test_basic_picked_on_an_agentic_model_is_its_default_without_a_chat(
    client: AsyncClient, engine: Engine
) -> None:
    """A refresh before the first message keeps the pick."""
    model = _select(engine, "anthropic/claude-haiku-4.5", "openrouter", OPENROUTER)

    picked = await client.put(
        "/llm/selection/text_gen/mode", json={"mode": "basic", **model}
    )

    assert picked.status_code == 200, picked.text
    modes = await _modes(client)
    assert (modes["default_mode"], modes["remembered_mode"]) == ("basic", "basic")


async def test_agentic_picked_on_a_model_that_cannot_run_it_is_refused_and_not_kept(
    client: AsyncClient, engine: Engine
) -> None:
    """The catalog says gpt-3.5-turbo makes no tool calls."""
    model = _select(engine, "gpt-3.5-turbo", "openai", OPENAI)

    picked = await client.put(
        "/llm/selection/text_gen/mode", json={"mode": "agentic", **model}
    )

    assert picked.status_code == 409, picked.text
    assert picked.json()["detail"]["code"] == "tool_calls_unsupported"
    modes = await _modes(client)
    assert (modes["default_mode"], modes["remembered_mode"]) == ("basic", None)


async def test_pick_made_on_a_model_no_longer_selected_is_refused_and_not_kept(
    client: AsyncClient, engine: Engine
) -> None:
    """The slot took another model, from this device or another, while the pick was on its way."""
    first = _select(engine, "anthropic/claude-haiku-4.5", "openrouter", OPENROUTER)
    _select(engine, "anthropic/claude-sonnet-4.5", "openrouter", OPENROUTER)

    picked = await client.put(
        "/llm/selection/text_gen/mode", json={"mode": "basic", **first}
    )

    assert picked.status_code == 409, picked.text
    assert picked.json()["detail"]["code"] == "model_changed"
    assert (await _modes(client))["remembered_mode"] is None


async def test_pick_on_a_local_model_with_no_connection_is_kept(
    client: AsyncClient, engine: Engine
) -> None:
    """A local model has no connection, and the selection read says so with a null."""
    with create_session_factory(engine)() as session:
        session.merge(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider=llamacpp.PROVIDER,
                name="Qwen3-0.6B",
            )
        )
        session.commit()

    picked = await client.put(
        "/llm/selection/text_gen/mode",
        json={
            "mode": "basic",
            "provider": llamacpp.PROVIDER,
            "connection_id": None,
            "name": "Qwen3-0.6B",
        },
    )

    assert picked.status_code == 200, picked.text
    assert picked.json()["remembered_mode"] == "basic"
