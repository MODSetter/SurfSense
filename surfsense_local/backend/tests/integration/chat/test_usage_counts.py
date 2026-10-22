"""A Basic chat turn counts an answer, by the kind of model, only once the model has written one.

Run on the stub encoder, so CI exercises the route's counting without the bundled model.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.usage_statistics.activity_counts import Activity, read_counts
from modules.usage_statistics.activity_counts.counts_file import start_counting
from modules.usage_statistics.dependencies import get_machine_readings
from shared.db import create_session_factory
from tests.integration.chat.test_folder_scope_end_to_end import (  # noqa: F401 (fixture)
    stub_encoder,
)
from tests.integration.usage_statistics.test_summary_route import MACHINE

# Every turn here searches on the stub encoder rather than the bundled model.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_encoder")]

# The model the stated machine holds, so a library that chose it reads as ready.
LOCAL_MODEL = "Qwen3-4B-Q4_K_M"


@pytest.fixture
async def client(engine: Engine) -> AsyncIterator[AsyncClient]:
    """The app over this test's library, on a stated machine, counting from the start."""
    start_counting(had_chats=False)
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN, provider="llamacpp", name=LOCAL_MODEL
            )
        )
        session.commit()
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    app.dependency_overrides[get_machine_readings] = lambda: MACHINE
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _ask(client: AsyncClient, text: str) -> None:
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread = (
        await client.post(f"/workspaces/{workspace['id']}/chat/threads", json={})
    ).json()
    async with client.stream(
        "POST", f"/chat/threads/{thread['id']}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200
        async for _line in reply.aiter_lines():
            pass


async def _week(client: AsyncClient) -> dict:
    since = datetime.now(UTC) - timedelta(days=7)
    response = await client.get(
        "/usage-statistics/summary", params={"since": since.isoformat()}
    )
    assert response.status_code == 200, response.text
    return response.json()["week"]


async def test_a_reply_from_the_local_model_counts_a_local_answer(
    client: AsyncClient, llamacpp_server: list[dict]
) -> None:
    """The count holds the kind of model and nothing of the question."""
    await _ask(client, "a question nobody else should read")

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.LOCAL_ANSWER, since) == 1
    assert counts.total(Activity.REMOTE_ANSWER, since) == 0
    assert "question" not in str(counts.hours)
    week = await _week(client)
    assert (week["model_source"], week["onboarding"]) == ("local", "first_answer")


async def test_a_turn_whose_model_fails_counts_no_answer(
    client: AsyncClient, llamacpp_server_unauthorized: None
) -> None:
    """The turn is still a chat turn, but setup has not reached its first answer."""
    await _ask(client, "will this be answered?")

    counts = read_counts()
    assert counts is not None
    assert (
        counts.total(Activity.LOCAL_ANSWER, datetime.now(UTC) - timedelta(hours=1)) == 0
    )
    assert not counts.answered
    week = await _week(client)
    assert (week["chat_turns"], week["model_source"]) == ("1-9", "none")
    assert week["onboarding"] == "model_ready"
