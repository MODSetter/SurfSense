"""A Basic chat turn is counted, on this machine, by the kind of model asked to answer."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.usage_statistics.activity_counts import Activity, read_counts
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


async def test_a_chat_turn_on_the_local_model_counts_a_local_answer(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The count holds the kind of model and nothing of the question."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
            )
        )
        session.commit()
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread = (
        await client.post(f"/workspaces/{workspace['id']}/chat/threads", json={})
    ).json()

    async with client.stream(
        "POST",
        f"/chat/threads/{thread['id']}/messages",
        json={"text": "a question nobody else should read"},
    ) as reply:
        assert reply.status_code == 200
        async for _line in reply.aiter_lines():
            pass

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.LOCAL_ANSWER, since) == 1
    assert counts.total(Activity.REMOTE_ANSWER, since) == 0
    assert "question" not in str(counts.hours)
