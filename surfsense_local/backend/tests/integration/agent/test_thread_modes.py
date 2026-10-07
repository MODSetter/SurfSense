"""Opening a chat in Basic (Q&A) or Agentic through the API: refusals leave no thread, and the choice is remembered."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.chat import router as chat_router
from modules.chat.models import ChatThread
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

OPENAI = "https://api.openai.com/v1"


@pytest.fixture(autouse=True)
def no_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app as it ships."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)


def _select(engine: Engine, name: str, catalog_provider: str = "openai") -> None:
    """A remote selection; nothing is sent to the host."""
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label="Remote",
            provider="openai_compatible",
            base_url=OPENAI,
            catalog_provider=catalog_provider,
        )
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name=name,
            )
        )
        session.commit()


def _thread_count(engine: Engine) -> int:
    with create_session_factory(engine)() as session:
        return session.query(ChatThread).count()


def _remembered(engine: Engine) -> dict | None:
    with create_session_factory(engine)() as session:
        selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        assert selected is not None
        return selected.settings


async def _open(client: AsyncClient, **fields: object) -> tuple[int, dict]:
    workspace = await client.post("/workspaces", json={"name": "Research"})
    workspace.raise_for_status()
    reply = await client.post(
        f"/workspaces/{workspace.json()['id']}/chat/threads",
        json={"title": "New chat", **fields},
    )
    return reply.status_code, reply.json()


async def test_basic_asked_for_opens_a_chat_and_is_remembered(
    client: AsyncClient, engine: Engine
) -> None:
    """The user's pick becomes the model's default for new chats."""
    _select(engine, "gpt-4o-mini")

    status, thread = await _open(client, mode="basic")

    assert status == 201
    assert thread["uses_agent"] is False
    assert _remembered(engine) == {"chat_mode": "basic"}
    capability = (await client.get("/llm/selection/text_gen")).json()["capability"]
    assert capability["modes"]["remembered_mode"] == "basic"


async def test_agentic_refused_by_a_gate_is_a_409_with_its_code_and_no_thread(
    client: AsyncClient, engine: Engine
) -> None:
    """The catalog says gpt-3.5-turbo makes no tool calls."""
    _select(engine, "gpt-3.5-turbo")

    status, body = await _open(client, mode="agentic")

    assert status == 409
    assert body["detail"]["code"] == "tool_calls_unsupported"
    assert _thread_count(engine) == 0
    assert _remembered(engine) is None


async def test_agentic_when_the_agent_does_not_start_is_a_503_and_no_thread(
    client: AsyncClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked for, it is never quietly a Basic chat instead."""

    async def not_ready(*_args: object) -> None:
        return None

    monkeypatch.setattr(chat_router, "open_agent_session", not_ready)
    _select(engine, "gpt-4o-mini")

    status, body = await _open(client, mode="agentic")

    assert status == 503
    assert body["detail"]["code"] == "agent_unavailable"
    assert _thread_count(engine) == 0


async def test_with_no_mode_a_model_whose_agent_does_not_start_opens_a_chat(
    client: AsyncClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An older client asked for nothing: the thread opens whatever state opencode is in."""

    async def not_ready(*_args: object) -> None:
        return None

    monkeypatch.setattr(chat_router, "open_agent_session", not_ready)
    _select(engine, "claude-opus-5-5", "anthropic")

    status, thread = await _open(client)

    assert status == 201
    assert thread["uses_agent"] is False
    # Nothing was chosen, so nothing is remembered.
    assert _remembered(engine) is None


async def test_a_mode_outside_the_two_is_refused(
    client: AsyncClient, engine: Engine
) -> None:
    """Basic or Agentic, nothing else."""
    _select(engine, "gpt-4o-mini")

    status, _body = await _open(client, mode="workflow")

    assert status == 422
    assert _thread_count(engine) == 0
