from __future__ import annotations

import json

import pytest
from langchain_core.exceptions import ContextOverflowError

from app.services.context_admission import (
    compute_tool_tokens,
    trim_messages_to_fit_context,
)
from app.services.llm_router_service import ChatLiteLLMRouter

pytestmark = pytest.mark.unit


def _count(messages: list[dict]) -> int:
    return len(json.dumps(messages)) // 4


def test_under_budget_messages_are_not_copied_or_changed() -> None:
    messages = [{"role": "user", "content": "hello"}]

    admitted, _, _ = trim_messages_to_fit_context(
        messages,
        count_tokens=_count,
        max_input_tokens=4_096,
    )

    assert admitted is messages


def test_protected_content_overflow_raises_instead_of_deleting_user_text() -> None:
    messages = [
        {"role": "system", "content": "S" * 2_000},
        {"role": "user", "content": "U" * 2_000},
    ]

    with pytest.raises(ContextOverflowError, match="cannot be truncated"):
        trim_messages_to_fit_context(
            messages,
            count_tokens=_count,
            max_input_tokens=600,
            output_reserve_fraction=0,
            preserve_protected_content=True,
        )

    assert messages[1]["content"] == "U" * 2_000


def test_protected_mode_can_omit_small_tool_outputs_before_failing() -> None:
    messages = [
        {"role": "system", "content": "system"},
        *[{"role": "tool", "content": "T" * 400} for _ in range(8)],
    ]

    admitted, final_tokens, budget = trim_messages_to_fit_context(
        messages,
        count_tokens=_count,
        max_input_tokens=600,
        output_reserve_fraction=0,
        preserve_protected_content=True,
    )

    assert final_tokens <= budget
    assert any(message["content"] != "T" * 400 for message in admitted[1:])


def test_router_mode_keeps_aggressive_fallback_for_unprotected_messages() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {"role": "assistant", "content": "A" * 4_000},
    ]

    admitted, final_tokens, budget = trim_messages_to_fit_context(
        messages,
        count_tokens=_count,
        max_input_tokens=600,
        output_reserve_fraction=0,
    )

    assert admitted[0] == messages[0]
    assert admitted[1]["content"] != messages[1]["content"]
    assert final_tokens <= budget


def test_router_method_preserves_shared_aggressive_trimming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = ChatLiteLLMRouter.model_construct()
    monkeypatch.setattr(ChatLiteLLMRouter, "_get_max_input_tokens", lambda _self: 600)
    monkeypatch.setattr(
        ChatLiteLLMRouter, "_count_tokens", lambda _self, messages: _count(messages)
    )
    messages = [
        {"role": "system", "content": "system"},
        {"role": "tool", "content": "T" * 4_000},
    ]

    admitted = router._trim_messages_to_fit_context(messages, output_reserve_fraction=0)

    assert admitted[0] == messages[0]
    assert admitted[1]["content"] != messages[1]["content"]
    assert _count(admitted) <= 600


_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "D" * 1_200,
        "parameters": {"type": "object", "properties": {}},
    },
}


def test_bound_tool_schemas_shrink_the_budget() -> None:
    """The provider charges for tool schemas, so admission must too -- otherwise
    a request passes locally and is rejected over the wire."""
    messages = [{"role": "user", "content": "hi"}]

    _, _, budget_without_tools = trim_messages_to_fit_context(
        messages,
        count_tokens=_count,
        max_input_tokens=8_960,
        output_reserve_fraction=0,
    )
    _, _, budget_with_tools = trim_messages_to_fit_context(
        messages,
        count_tokens=_count,
        max_input_tokens=8_960,
        output_reserve_fraction=0,
        reserved_tokens=compute_tool_tokens([_TOOL_SCHEMA] * 4, _count),
    )

    reserved = compute_tool_tokens([_TOOL_SCHEMA] * 4, _count)
    assert reserved > 0
    assert budget_without_tools - budget_with_tools == reserved


def test_compute_tool_tokens_ignores_absent_or_unserializable_tools() -> None:
    assert compute_tool_tokens(None, _count) == 0
    assert compute_tool_tokens([], _count) == 0
    # default=str keeps an exotic schema from raising; it just gets counted.
    assert compute_tool_tokens([{"fn": object()}], _count) > 0


def test_router_method_reserves_tokens_for_its_bound_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = ChatLiteLLMRouter.model_construct()
    object.__setattr__(router, "_bound_tools", [_TOOL_SCHEMA])
    monkeypatch.setattr(ChatLiteLLMRouter, "_get_max_input_tokens", lambda _self: 1_200)
    monkeypatch.setattr(
        ChatLiteLLMRouter, "_count_tokens", lambda _self, messages: _count(messages)
    )
    messages = [{"role": "tool", "content": "T" * 3_000}]

    admitted = router._trim_messages_to_fit_context(messages, output_reserve_fraction=0)

    assert _count(admitted) <= 1_200 - compute_tool_tokens([_TOOL_SCHEMA], _count)


def test_router_method_preserves_passthrough_when_all_tokenizers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = ChatLiteLLMRouter.model_construct()
    monkeypatch.setattr(ChatLiteLLMRouter, "_get_max_input_tokens", lambda _self: 600)
    monkeypatch.setattr(
        ChatLiteLLMRouter, "_count_tokens", lambda _self, _messages: None
    )
    messages = [{"role": "tool", "content": "T" * 4_000}]

    admitted = router._trim_messages_to_fit_context(messages)

    assert admitted is messages
