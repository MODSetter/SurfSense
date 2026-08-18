"""Commit messages: model-generated subject, deterministic fallback."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence import (
    commit_message as commit_message_module,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_message import (
    fallback_commit_message,
    generate_commit_message,
)

pytestmark = pytest.mark.unit


class _BrokenModel:
    async def ainvoke(self, _input, config=None, **kwargs):
        raise RuntimeError("model down")


class _StalledModel:
    """Accepts the request, then never answers — a hang, not a failure."""

    async def ainvoke(self, _input, config=None, **kwargs):
        await asyncio.sleep(3600)


class _CapturingModel:
    """Records the config it was invoked with, then answers normally."""

    def __init__(self) -> None:
        self.config: dict | None = None

    async def ainvoke(self, _input, config=None, **kwargs):
        self.config = config
        return SimpleNamespace(content="docs: capture")


async def test_uses_the_models_reply_as_subject():
    llm = FakeListChatModel(responses=["docs: add meeting notes\n"])
    message = await generate_commit_message(
        llm, writes={"documents/notes.md": b"# Notes"}, removes=[]
    )
    assert message == "docs: add meeting notes"


async def test_a_reasoning_models_thinking_never_reaches_the_subject():
    """Reasoning models answer in blocks; the shape below is a real reply."""

    class _ReasoningModel:
        async def ainvoke(self, _input, config=None, **kwargs):
            return SimpleNamespace(
                content=[
                    {"type": "thinking", "thinking": "**Inferring commit message**"},
                    {"type": "thinking", "thinking": " the user wants a leaf image"},
                    "docs: add simple green leaf image prompt",
                ]
            )

    message = await generate_commit_message(
        _ReasoningModel(), writes={"documents/leaf.md": b"# Leaf"}, removes=[]
    )
    assert message == "docs: add simple green leaf image prompt"


async def test_falls_back_deterministically_when_the_model_fails():
    message = await generate_commit_message(
        _BrokenModel(),
        writes={"a.md": b"1", "b.md": b"2"},
        removes=["c.md"],
    )
    assert message == fallback_commit_message(
        writes={"a.md": b"1", "b.md": b"2"}, removes=["c.md"]
    )


async def test_a_stalled_model_does_not_hold_the_commit(monkeypatch):
    monkeypatch.setattr(
        commit_message_module, "_GENERATION_TIMEOUT_SECONDS", 0.05, raising=True
    )
    message = await asyncio.wait_for(
        generate_commit_message(_StalledModel(), writes={"a.md": b"1"}, removes=[]),
        timeout=5,
    )
    assert message == fallback_commit_message(writes={"a.md": b"1"}, removes=[])


async def test_subject_generation_is_tagged_internal_so_it_does_not_stream():
    """The subject shares the agent's streaming llm; the internal tag is what
    keeps its tokens out of the user's reply (chat_model_stream drops them)."""
    llm = _CapturingModel()
    await generate_commit_message(llm, writes={"a.md": b"1"}, removes=[])
    assert "surfsense:internal" in (llm.config or {}).get("tags", [])


async def test_no_model_uses_the_deterministic_subject():
    message = await generate_commit_message(None, writes={"a.md": b"1"}, removes=[])
    assert message == fallback_commit_message(writes={"a.md": b"1"}, removes=[])


def test_fallback_names_the_change_counts():
    message = fallback_commit_message(writes={"a.md": b"1"}, removes=["b.md", "c.md"])
    assert "1" in message
    assert "2" in message
