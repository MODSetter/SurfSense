"""Commit messages: model-generated subject, deterministic fallback."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_message import (
    fallback_commit_message,
    generate_commit_message,
)

pytestmark = pytest.mark.unit


class _BrokenModel:
    async def ainvoke(self, _input):
        raise RuntimeError("model down")


async def test_uses_the_models_reply_as_subject():
    llm = FakeListChatModel(responses=["docs: add meeting notes\n"])
    message = await generate_commit_message(
        llm, writes={"documents/notes.md": b"# Notes"}, removes=[]
    )
    assert message == "docs: add meeting notes"


async def test_falls_back_deterministically_when_the_model_fails():
    message = await generate_commit_message(
        _BrokenModel(),
        writes={"a.md": b"1", "b.md": b"2"},
        removes=["c.md"],
    )
    assert message == fallback_commit_message(
        writes={"a.md": b"1", "b.md": b"2"}, removes=["c.md"]
    )


async def test_no_model_uses_the_deterministic_subject():
    message = await generate_commit_message(None, writes={"a.md": b"1"}, removes=[])
    assert message == fallback_commit_message(writes={"a.md": b"1"}, removes=[])


def test_fallback_names_the_change_counts():
    message = fallback_commit_message(writes={"a.md": b"1"}, removes=["b.md", "c.md"])
    assert "1" in message
    assert "2" in message
