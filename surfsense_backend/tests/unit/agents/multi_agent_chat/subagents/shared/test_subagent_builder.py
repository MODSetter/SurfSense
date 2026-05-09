"""Subagent resilience contract: ``extra_middleware`` reaches the agent chain."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agents.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)


class RateLimitError(Exception):
    """Name matches the scoped-fallback eligibility allowlist."""


class _AlwaysFailingChatModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "always-failing-test-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = "primary llm exploded"
        raise RateLimitError(msg)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = "primary llm exploded"
        raise RateLimitError(msg)

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGeneration]:
        msg = "primary llm exploded"
        raise RateLimitError(msg)

    async def _astream(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGeneration]:
        msg = "primary llm exploded"
        raise RateLimitError(msg)
        yield  # pragma: no cover - unreachable, satisfies async generator typing


@pytest.mark.asyncio
async def test_subagent_recovers_when_primary_llm_fails():
    """Fallback in ``extra_middleware`` must finish the turn when primary raises."""
    primary = _AlwaysFailingChatModel()
    fallback = FakeMessagesListChatModel(
        responses=[AIMessage(content="recovered via fallback")]
    )

    spec = pack_subagent(
        name="resilience_test",
        description="test subagent",
        system_prompt="be helpful",
        tools=[],
        model=primary,
        extra_middleware=[ModelFallbackMiddleware(fallback)],
    )

    agent = create_agent(
        model=spec["model"],
        tools=spec["tools"],
        middleware=spec["middleware"],
        system_prompt=spec["system_prompt"],
    )

    result = await agent.ainvoke({"messages": [HumanMessage(content="hi")]})

    final = result["messages"][-1]
    assert isinstance(final, AIMessage)
    assert final.content == "recovered via fallback"
