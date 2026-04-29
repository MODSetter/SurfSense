"""Tests for NoopInjectionMiddleware provider-compat logic."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.new_chat.middleware.noop_injection import (
    NOOP_TOOL_NAME,
    NoopInjectionMiddleware,
    _last_ai_has_tool_calls,
    _provider_needs_noop,
)

pytestmark = pytest.mark.unit


class _LiteLLMModel:
    def _get_ls_params(self):
        return {"ls_provider": "litellm"}


class _BedrockModel:
    def _get_ls_params(self):
        return {"ls_provider": "bedrock"}


class _OpenAIModel:
    def _get_ls_params(self):
        return {"ls_provider": "openai"}


class _ChatLiteLLM:  # name-only fallback
    pass


class TestProviderDetection:
    def test_litellm(self) -> None:
        assert _provider_needs_noop(_LiteLLMModel()) is True

    def test_bedrock(self) -> None:
        assert _provider_needs_noop(_BedrockModel()) is True

    def test_openai_does_not_need(self) -> None:
        assert _provider_needs_noop(_OpenAIModel()) is False

    def test_class_name_fallback(self) -> None:
        assert _provider_needs_noop(_ChatLiteLLM()) is True


class TestHistoryDetection:
    def test_last_ai_has_tool_calls(self) -> None:
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
        ]
        assert _last_ai_has_tool_calls(msgs) is True

    def test_last_ai_no_tool_calls(self) -> None:
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="hello"),
        ]
        assert _last_ai_has_tool_calls(msgs) is False

    def test_no_ai_in_history(self) -> None:
        assert _last_ai_has_tool_calls([HumanMessage(content="hi")]) is False


class _FakeRequest:
    def __init__(self, *, tools, messages, model) -> None:
        self.tools = tools
        self.messages = messages
        self.model = model

    def override(self, *, tools):
        return _FakeRequest(tools=tools, messages=self.messages, model=self.model)


class TestShouldInject:
    def test_injects_when_all_conditions_met(self) -> None:
        mw = NoopInjectionMiddleware()
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
        ]
        req = _FakeRequest(tools=[], messages=msgs, model=_LiteLLMModel())
        assert mw._should_inject(req) is True

    def test_skips_when_tools_present(self) -> None:
        mw = NoopInjectionMiddleware()
        req = _FakeRequest(
            tools=[object()],
            messages=[
                AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
            ],
            model=_LiteLLMModel(),
        )
        assert mw._should_inject(req) is False

    def test_skips_when_no_history_tool_calls(self) -> None:
        mw = NoopInjectionMiddleware()
        req = _FakeRequest(
            tools=[],
            messages=[HumanMessage(content="hi")],
            model=_LiteLLMModel(),
        )
        assert mw._should_inject(req) is False

    def test_skips_for_openai(self) -> None:
        mw = NoopInjectionMiddleware()
        req = _FakeRequest(
            tools=[],
            messages=[
                AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
            ],
            model=_OpenAIModel(),
        )
        assert mw._should_inject(req) is False


def test_noop_tool_name_is_underscore_noop() -> None:
    assert NOOP_TOOL_NAME == "_noop"
