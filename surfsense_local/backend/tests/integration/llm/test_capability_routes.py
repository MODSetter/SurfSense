"""What the screens are told of a model's measured capability, and the user's opt-in to try the agent."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.db import create_session_factory

from . import conftest

pytestmark = pytest.mark.integration

URL = "/llm/selection/text_gen/agent-trial"
OPENROUTER = "https://openrouter.ai/api/v1"


def _select(engine: Engine, name: str, catalog_provider: str, base_url: str) -> None:
    """A remote selection written as the selection route leaves it; nothing is sent to the host."""
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


async def _capability(client: AsyncClient) -> dict:
    reply = await client.get("/llm/selection/text_gen")
    assert reply.status_code == 200, reply.text
    return reply.json()["capability"]


async def test_a_measured_model_says_its_level_and_the_row_behind_it(
    client: AsyncClient, engine: Engine
) -> None:
    """The level, its reason as a code with values, and the evidence line."""
    _select(engine, "anthropic/claude-haiku-4.5", "openrouter", OPENROUTER)

    capability = await _capability(client)

    assert capability["level"] == "agent_limited"
    assert capability["label_key"] == "agent_limited"
    assert capability["reason"] == {
        "code": "measured_near",
        "values": {
            "passed": 5,
            "counted": 8,
            "suite_version": 1,
            "measured_on": "2026-10-04",
        },
    }
    assert capability["note"]
    assert capability["measured"] == {
        "key": "claude-haiku-4-5",
        "suite_version": 1,
        "measured_on": "2026-10-04",
        "provider": "anthropic",
        "host": "api.anthropic.com",
        "reads_images": True,
        "passed": 5,
        "counted": 8,
        "provisional": True,
    }
    assert capability["agent_trial"] == {
        "offered": False,
        "enabled": False,
        "blocked": None,
    }


async def test_an_unmeasured_model_that_calls_tools_is_offered_the_trial(
    client: AsyncClient, engine: Engine
) -> None:
    """Off until the user turns it on."""
    _select(engine, "gpt-4o-mini", "openai", "https://api.openai.com/v1")

    capability = await _capability(client)

    assert capability["level"] == "not_measured"
    assert capability["reason"] == {"code": "no_row", "values": {}}
    assert capability["measured"] is None
    assert capability["agent_trial"] == {
        "offered": True,
        "enabled": False,
        "blocked": None,
    }


async def test_the_trial_is_kept_on_the_model_once_turned_on_and_off_again(
    client: AsyncClient, engine: Engine
) -> None:
    """Stored on the selection, so every read says it."""
    _select(engine, "gpt-4o-mini", "openai", "https://api.openai.com/v1")

    on = await client.put(URL, json={"enabled": True})
    assert on.status_code == 200, on.text
    assert on.json()["agent_trial"]["enabled"] is True
    assert (await _capability(client))["agent_trial"]["enabled"] is True

    off = await client.put(URL, json={"enabled": False})
    assert off.json()["agent_trial"]["enabled"] is False


async def test_a_model_whose_tool_calls_nothing_confirms_cannot_be_opted_in(
    client: AsyncClient, engine: Engine
) -> None:
    """Offered nowhere it would fail at the first step."""
    _select(engine, "anthropic/claude-sonnet-99", "openrouter", OPENROUTER)

    assert (await _capability(client))["agent_trial"] == {
        "offered": False,
        "enabled": False,
        "blocked": "tool_calls_unconfirmed",
    }
    refused = await client.put(URL, json={"enabled": True})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "tool_calls_unconfirmed"


async def test_a_measured_model_takes_no_opt_in(
    client: AsyncClient, engine: Engine
) -> None:
    """Its level decides: a pass runs the agent already, a failure never does."""
    _select(engine, "google/gemma-4-31b-it", "openrouter", OPENROUTER)

    refused = await client.put(URL, json={"enabled": True})

    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "measured"


async def test_the_trial_goes_when_the_slot_takes_another_model(
    client: AsyncClient, engine: Engine, llamacpp_server: str
) -> None:
    """It belongs to the model it was given for."""
    _select(engine, "gpt-4o-mini", "openai", "https://api.openai.com/v1")
    await client.put(URL, json={"enabled": True})

    chosen = await client.put(
        "/llm/selection/text_gen",
        json={"provider": "llamacpp", "name": "Qwen3-4B-Q4_K_M"},
    )

    assert chosen.status_code == 200, chosen.text
    # A local model's tool calls are read when a chat starts, not on every read.
    assert chosen.json()["capability"]["agent_trial"] == {
        "offered": True,
        "enabled": False,
        "blocked": None,
    }


async def test_no_text_model_has_no_trial_to_set(client: AsyncClient) -> None:
    """There is nothing to keep it on."""
    assert (await client.put(URL, json={"enabled": True})).status_code == 404


async def test_the_model_lists_carry_each_chat_model_s_level(
    client: AsyncClient,
    openai_server: str,
    llamacpp_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure holds on any host; a model that fills no chat slot has no level."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [*conftest.REMOTE_MODELS, {"id": "qwen/qwen3.5-9b"}]
    )
    connection = await client.post(
        "/llm/connections",
        json={
            "label": "Gateway",
            "provider": "openai_compatible",
            "base_url": openai_server,
            "catalog_provider": "openrouter",
        },
    )
    assert connection.status_code == 201, connection.text

    remote = {
        m["name"]: m["capability_level"]
        for m in (
            await client.get(f"/llm/connections/{connection.json()['id']}/models")
        ).json()
    }
    local = {
        m["name"]: m["capability_level"]
        for m in (await client.get("/llm/providers/llamacpp/models")).json()
    }

    assert remote == {
        "anthropic/claude-3.5-sonnet": "not_measured",
        "black-forest-labs/flux": None,
        "qwen/qwen3.5-9b": "studio_only",
    }
    assert set(local.values()) == {"not_measured"}
