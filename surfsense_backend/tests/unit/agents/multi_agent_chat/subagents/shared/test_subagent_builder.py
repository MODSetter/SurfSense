"""Subagent resilience contract: ``middleware_stack`` reaches the agent chain."""

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

from app.agents.multi_agent_chat.shared.middleware.permissions.middleware.core import (
    PermissionMiddleware,
)
from app.agents.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)
from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.shared.permissions import Rule, Ruleset, evaluate


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
    """Fallback in ``middleware_stack`` must finish the turn when primary raises."""
    primary = _AlwaysFailingChatModel()
    fallback = FakeMessagesListChatModel(
        responses=[AIMessage(content="recovered via fallback")]
    )

    result = pack_subagent(
        name="resilience_test",
        description="test subagent",
        system_prompt="be helpful",
        tools=[],
        ruleset=Ruleset(origin="resilience_test", rules=[]),
        dependencies={"flags": AgentFeatureFlags()},
        model=primary,
        middleware_stack={"fallback": ModelFallbackMiddleware(fallback)},
    )
    spec = result.spec

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


def _extract_permission_mw(spec) -> PermissionMiddleware:
    """Find the lone PermissionMiddleware in a subagent's middleware list."""
    matches = [m for m in spec["middleware"] if isinstance(m, PermissionMiddleware)]
    assert len(matches) == 1, "expected exactly one PermissionMiddleware"
    return matches[0]


def test_user_allowlist_overrides_coded_ask_via_last_match_wins():
    """User ``allow`` rules promoted via "Always Allow" must beat coded ``ask`` rules."""
    coded = Ruleset(
        origin="connector",
        rules=[Rule(permission="save_issue", pattern="*", action="ask")],
    )
    user_allowlist = Ruleset(
        origin="user_allowlist:connector",
        rules=[Rule(permission="save_issue", pattern="*", action="allow")],
    )

    result = pack_subagent(
        name="connector",
        description="test connector",
        system_prompt="x",
        tools=[],
        ruleset=coded,
        dependencies={
            "flags": AgentFeatureFlags(),
            "user_allowlist_by_subagent": {"connector": user_allowlist},
        },
    )

    mw = _extract_permission_mw(result.spec)
    decided = evaluate("save_issue", "*", *mw._static_rulesets)
    assert decided.action == "allow", (
        f"user_allowlist must override coded ask; got {decided!r}"
    )


def test_coded_ask_stays_when_user_allowlist_unrelated():
    """User ``allow`` rules for OTHER tools must not leak into asked-tools."""
    coded = Ruleset(
        origin="connector",
        rules=[Rule(permission="delete_issue", pattern="*", action="ask")],
    )
    user_allowlist = Ruleset(
        origin="user_allowlist:connector",
        rules=[Rule(permission="save_issue", pattern="*", action="allow")],
    )

    result = pack_subagent(
        name="connector",
        description="test",
        system_prompt="x",
        tools=[],
        ruleset=coded,
        dependencies={
            "flags": AgentFeatureFlags(),
            "user_allowlist_by_subagent": {"connector": user_allowlist},
        },
    )

    mw = _extract_permission_mw(result.spec)
    decided = evaluate("delete_issue", "*", *mw._static_rulesets)
    assert decided.action == "ask"


def test_missing_user_allowlist_keeps_coded_behaviour():
    """``dependencies`` without ``user_allowlist_by_subagent`` is the common case."""
    coded = Ruleset(
        origin="connector",
        rules=[Rule(permission="save_issue", pattern="*", action="ask")],
    )

    result = pack_subagent(
        name="connector",
        description="test",
        system_prompt="x",
        tools=[],
        ruleset=coded,
        dependencies={"flags": AgentFeatureFlags()},
    )

    mw = _extract_permission_mw(result.spec)
    decided = evaluate("save_issue", "*", *mw._static_rulesets)
    assert decided.action == "ask"


def test_user_allowlist_for_different_subagent_does_not_leak():
    """User trust for ``linear`` must not affect a ``jira`` subagent compile."""
    coded = Ruleset(
        origin="jira",
        rules=[Rule(permission="save_issue", pattern="*", action="ask")],
    )
    linear_allowlist = Ruleset(
        origin="user_allowlist:linear",
        rules=[Rule(permission="save_issue", pattern="*", action="allow")],
    )

    result = pack_subagent(
        name="jira",
        description="test",
        system_prompt="x",
        tools=[],
        ruleset=coded,
        dependencies={
            "flags": AgentFeatureFlags(),
            "user_allowlist_by_subagent": {"linear": linear_allowlist},
        },
    )

    mw = _extract_permission_mw(result.spec)
    decided = evaluate("save_issue", "*", *mw._static_rulesets)
    assert decided.action == "ask"


def test_empty_user_allowlist_is_tolerated():
    """An empty ``Ruleset`` (no rules) must not flip evaluation to allow-everything."""
    coded = Ruleset(
        origin="connector",
        rules=[Rule(permission="save_issue", pattern="*", action="ask")],
    )
    empty = Ruleset(origin="user_allowlist:connector", rules=[])

    result = pack_subagent(
        name="connector",
        description="test",
        system_prompt="x",
        tools=[],
        ruleset=coded,
        dependencies={
            "flags": AgentFeatureFlags(),
            "user_allowlist_by_subagent": {"connector": empty},
        },
    )

    mw = _extract_permission_mw(result.spec)
    decided = evaluate("save_issue", "*", *mw._static_rulesets)
    assert decided.action == "ask"
