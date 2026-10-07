"""What the screens are told of a model's measured capability, and the modes a new chat on it may take."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings
from shared.db import create_session_factory

from . import conftest

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


def _select(
    engine: Engine,
    name: str,
    catalog_provider: str,
    base_url: str,
    settings: dict | None = None,
) -> None:
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
                settings=settings,
            )
        )
        session.commit()


async def _capability(client: AsyncClient) -> dict:
    reply = await client.get("/llm/selection/text_gen")
    assert reply.status_code == 200, reply.text
    return reply.json()["capability"]


async def test_a_measured_model_says_its_level_the_row_behind_it_and_starts_agentic(
    client: AsyncClient, engine: Engine
) -> None:
    """The level, its reason as a code with values, the evidence line and the modes."""
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
        "suite": "create-and-edit",
        "assumed": False,
        "suite_version": 1,
        "measured_on": "2026-10-04",
        "provider": "anthropic",
        "host": "api.anthropic.com",
        "reads_images": True,
        "passed": 5,
        "counted": 8,
        "provisional": True,
    }
    assert capability["modes"] == {
        "agentic_allowed": True,
        "blocked": None,
        "default_mode": "agentic",
        "reason": {"code": "measured_near", "values": {"passed": 5, "counted": 8}},
        "remembered_mode": None,
    }


async def test_a_low_scorer_starts_basic_and_is_offered_agentic_with_its_score(
    client: AsyncClient, engine: Engine
) -> None:
    """Gemma 4 31B passed 2 of 8: Agentic stays one choice away."""
    _select(engine, "google/gemma-4-31b-it", "openrouter", OPENROUTER)

    modes = (await _capability(client))["modes"]

    assert modes["agentic_allowed"] is True
    assert modes["default_mode"] == "basic"
    assert modes["reason"] == {
        "code": "measured_below",
        "values": {"passed": 2, "counted": 8},
    }


@pytest.mark.parametrize(
    ("name", "catalog_provider", "base_url"),
    [
        # Made up, so no sweep the list takes in can give it a row.
        ("gpt-99-mini", "openai", OPENAI),
        # The catalog says nothing of its tool calls, which is not a no.
        ("anthropic/claude-sonnet-99", "openrouter", OPENROUTER),
    ],
)
async def test_an_untested_model_starts_basic_and_is_offered_agentic(
    client: AsyncClient, engine: Engine, name: str, catalog_provider: str, base_url: str
) -> None:
    """With the untested warning, never refused."""
    _select(engine, name, catalog_provider, base_url)

    capability = await _capability(client)

    assert capability["level"] == "not_measured"
    assert capability["measured"] is None
    assert capability["modes"] == {
        "agentic_allowed": True,
        "blocked": None,
        "default_mode": "basic",
        "reason": {"code": "untested", "values": {}},
        "remembered_mode": None,
    }


async def test_a_model_that_cannot_call_tools_is_not_offered_agentic(
    client: AsyncClient, engine: Engine
) -> None:
    """The catalog records `tool_call: false`; the reason goes with the disabled option."""
    _select(engine, "gpt-3.5-turbo", "openai", OPENAI)

    modes = (await _capability(client))["modes"]

    assert (modes["agentic_allowed"], modes["blocked"]) == (
        False,
        "tool_calls_unsupported",
    )
    assert modes["default_mode"] == "basic"


async def test_without_opencode_agentic_is_not_installed(
    client: AsyncClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build that stages no opencode offers Basic alone."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)
    _select(engine, "claude-opus-5-5", "anthropic", "https://api.anthropic.com/v1")

    modes = (await _capability(client))["modes"]

    assert (modes["agentic_allowed"], modes["blocked"]) == (
        False,
        "agent_not_installed",
    )
    assert modes["default_mode"] == "basic"


async def test_the_old_agent_trial_reads_as_agentic_remembered(
    client: AsyncClient, engine: Engine
) -> None:
    """A model the user turned "Try the agent" on for keeps starting Agentic."""
    _select(engine, "gpt-4o-mini", "openai", OPENAI, settings={"agent_trial": True})

    modes = (await _capability(client))["modes"]

    assert (modes["remembered_mode"], modes["default_mode"]) == ("agentic", "agentic")


async def test_a_model_s_remembered_mode_waits_while_the_slot_holds_another(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """It belongs to the model it was chosen for, and comes back with it."""

    async def select(name: str) -> dict:
        chosen = await client.put(
            "/llm/selection/text_gen", json={"provider": "llamacpp", "name": name}
        )
        assert chosen.status_code == 200, chosen.text
        return chosen.json()["capability"]["modes"]

    await select("Qwen3-4B-Q4_K_M")
    workspace = (await client.post("/workspaces", json={"name": "Research"})).json()
    opened = await client.post(
        f"/workspaces/{workspace['id']}/chat/threads",
        json={"title": "New chat", "mode": "basic", "remember": True},
    )
    assert opened.status_code == 201, opened.text

    other = await select("Qwen3-1.7B-Q4_K_M")
    back = await select("Qwen3-4B-Q4_K_M")

    # A local model's tool calls are read when a chat starts, not on every read.
    assert other == {
        "agentic_allowed": True,
        "blocked": None,
        "default_mode": "basic",
        "reason": {"code": "untested", "values": {}},
        "remembered_mode": None,
    }
    assert back["remembered_mode"] == "basic"


async def test_the_agent_trial_route_is_gone(
    client: AsyncClient, engine: Engine
) -> None:
    """The composer's mode switch replaced it."""
    _select(engine, "gpt-4o-mini", "openai", OPENAI)

    reply = await client.put(
        "/llm/selection/text_gen/agent-trial", json={"enabled": True}
    )

    assert reply.status_code in (404, 405)


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
