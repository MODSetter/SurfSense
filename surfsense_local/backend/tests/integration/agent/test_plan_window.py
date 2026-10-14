"""A ChatGPT plan's model has the window the plan states, not the API's own."""

import pytest
from sqlalchemy import Engine

from modules.agent.model_window import selected_model_window
from shared.db import create_session_factory
from tests.integration.llm.chatgpt.fake_openai import FakeOpenAI

from .test_responses_relay import select_plan

pytestmark = pytest.mark.integration


async def test_the_plans_window_sets_the_agents_limits(
    engine: Engine,
    fake_openai: FakeOpenAI,
) -> None:
    """The catalog records gpt-5's API window, 400,000; the plan serves it with less."""
    fake_openai.live_access.add("at-live")
    fake_openai.models = [
        {"slug": "gpt-5", "visibility": "list", "context_window": 272000}
    ]
    sessions = create_session_factory(engine)
    select_plan(sessions, f"{fake_openai.url}/v1", "at-live", "rt-1")

    with sessions() as session:
        assert await selected_model_window(session) == ("gpt-5", 272000)


async def test_without_the_plans_word_the_catalog_window_stands(
    engine: Engine,
    fake_openai: FakeOpenAI,
) -> None:
    """A plan list that states no window leaves the catalog's."""
    fake_openai.live_access.add("at-live")
    sessions = create_session_factory(engine)
    select_plan(sessions, f"{fake_openai.url}/v1", "at-live", "rt-1")

    with sessions() as session:
        assert await selected_model_window(session) == ("gpt-5", 400000)
