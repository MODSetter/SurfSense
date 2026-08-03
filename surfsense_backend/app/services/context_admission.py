"""Shared model-context counting, trimming, and admission helpers."""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Callable
from typing import Any

from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

TokenCounter = Callable[[list[dict[str, Any]]], int | None]


def _env_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name) or default)
    except ValueError:
        return default
    return value if value > 0 else default


# Budget for a model no source can size. Env-overridable so a deployment behind
# a gateway of models LiteLLM has never heard of can raise it in one place
# instead of editing every model by hand.
GEN_AI_MODEL_FALLBACK_MAX_TOKENS = _env_positive_int(
    "GEN_AI_MODEL_FALLBACK_MAX_TOKENS", 32_000
)

_TRIM_SUFFIX = (
    "\n\n<!-- Content trimmed to fit model context window. "
    "Some documents were omitted. Refine your query or "
    "reduce top_k for different results. -->"
)


def conservative_token_estimate(messages: list[dict[str, Any]]) -> int:
    """Estimate tokens conservatively when the selected tokenizer is unavailable."""
    serialized = json.dumps(messages, ensure_ascii=False, default=str)
    return max(1, (len(serialized) + 2) // 3)


def convert_langchain_messages(
    messages: list[BaseMessage],
    sanitize_content: Callable[[Any], Any],
) -> list[dict[str, Any]]:
    """Convert LangChain messages to the OpenAI representation used for counting."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            ai_msg: dict[str, Any] = {"role": "assistant"}
            sanitized = sanitize_content(msg.content) if msg.content else ""
            ai_msg["content"] = sanitized if sanitized else ""
            if msg.tool_calls:
                ai_msg["tool_calls"] = [
                    {
                        "id": tool_call.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tool_call.get("name", ""),
                            "arguments": (
                                tool_call.get("args", "{}")
                                if isinstance(tool_call.get("args"), str)
                                else json.dumps(tool_call.get("args", {}))
                            ),
                        },
                    }
                    for tool_call in msg.tool_calls
                ]
            result.append(ai_msg)
        elif isinstance(msg, ToolMessage):
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": (
                        msg.content
                        if isinstance(msg.content, str)
                        else json.dumps(msg.content)
                    ),
                }
            )
        else:
            role = getattr(msg, "type", "user")
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
            result.append({"role": role, "content": msg.content})
    return result


def _count(
    messages: list[dict[str, Any]],
    count_tokens: TokenCounter,
    *,
    estimate_on_failure: bool,
) -> int | None:
    counted = count_tokens(messages)
    if counted is not None:
        return counted
    return conservative_token_estimate(messages) if estimate_on_failure else None


def compute_tool_tokens(tools: Any, count_tokens: TokenCounter) -> int:
    """Count the tokens a bound tool-schema payload adds to every request.

    ``litellm.token_counter`` is given only ``messages``, so without this the
    schemas are budgeted as zero and an oversized request passes local
    admission just to be rejected by the provider, which does charge them.
    Each schema is counted as a lone user message, so the reservation includes
    that message's framing overhead per tool -- erring toward reserving
    slightly too much rather than too little.
    """
    if not isinstance(tools, list) or not tools:
        return 0
    total = 0
    for tool in tools:
        try:
            serialized = json.dumps(tool, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            continue
        total += (
            _count(
                [{"role": "user", "content": serialized}],
                count_tokens,
                estimate_on_failure=True,
            )
            or 0
        )
    return total


def trim_messages_to_fit_context(
    messages: list[dict[str, Any]],
    *,
    count_tokens: TokenCounter,
    max_input_tokens: int,
    output_reserve_fraction: float = 0.10,
    minimum_output_reserve: int = 0,
    safety_margin_fraction: float = 0.0,
    reserved_tokens: int = 0,
    preserve_protected_content: bool = False,
    estimate_on_count_failure: bool = True,
) -> tuple[list[dict[str, Any]], int, int]:
    """Fit messages to a context budget while preserving router compatibility.

    ``reserved_tokens`` covers request parts the token counter never sees --
    today, the bound tool schemas.
    """
    output_reserve = max(
        minimum_output_reserve,
        min(int(max_input_tokens * output_reserve_fraction), 16_384),
    )
    safety_margin = int(max_input_tokens * safety_margin_fraction)
    budget = max(
        0, max_input_tokens - output_reserve - safety_margin - max(0, reserved_tokens)
    )
    total_tokens = _count(
        messages,
        count_tokens,
        estimate_on_failure=estimate_on_count_failure,
    )
    if total_tokens is None:
        return messages, 0, budget
    if total_tokens <= budget:
        return messages, total_tokens, budget

    trimmed = copy.deepcopy(messages)
    message_token_map: dict[int, int] = {}
    candidate_priority: dict[int, int] = {}
    for index, message in enumerate(trimmed):
        if message.get("role") == "system":
            continue
        role = message.get("role")
        content = message.get("content", "")
        if not isinstance(content, str) or len(content) < 500:
            continue
        is_document = "<document>" in content or "<mentioned_documents>" in content
        if role in ("tool", "assistant"):
            candidate_priority[index] = 0
        elif role == "user" and is_document:
            candidate_priority[index] = 1
        else:
            continue
        message_tokens = _count(
            [message],
            count_tokens,
            estimate_on_failure=estimate_on_count_failure,
        )
        if message_tokens is not None:
            message_token_map[index] = message_tokens

    candidates = sorted(
        message_token_map.items(),
        key=lambda item: (candidate_priority.get(item[0], 9), -item[1]),
    )
    running_total = total_tokens
    for index, original_message_tokens in candidates:
        if running_total <= budget:
            break

        content = trimmed[index]["content"]
        original_length = len(content)
        low, high = 200, original_length - 1
        best = 200
        while low <= high:
            midpoint = (low + high) // 2
            trimmed[index]["content"] = content[:midpoint] + _TRIM_SUFFIX
            new_message_tokens = _count(
                [trimmed[index]],
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            if new_message_tokens is None:
                high = midpoint - 1
                continue
            projected_total = (
                running_total - original_message_tokens + new_message_tokens
            )
            if projected_total <= budget:
                best = midpoint
                low = midpoint + 1
            else:
                high = midpoint - 1

        last_document_end = content[:best].rfind("</document>")
        if last_document_end > min(200, best // 4):
            best = last_document_end + len("</document>")
        trimmed[index]["content"] = content[:best] + _TRIM_SUFFIX
        new_message_tokens = _count(
            [trimmed[index]],
            count_tokens,
            estimate_on_failure=estimate_on_count_failure,
        )
        if new_message_tokens is None:
            continue
        running_total = running_total - original_message_tokens + new_message_tokens

    recounted = _count(
        trimmed,
        count_tokens,
        estimate_on_failure=estimate_on_count_failure,
    )
    if recounted is not None:
        running_total = recounted
    if running_total <= budget:
        return trimmed, running_total, budget
    if preserve_protected_content:
        removable_indices = [
            index
            for index, message in enumerate(trimmed)
            if isinstance(message.get("content"), str)
            and message["content"]
            and (
                message.get("role") in ("tool", "assistant")
                or (
                    message.get("role") == "user"
                    and (
                        "<document>" in message["content"]
                        or "<mentioned_documents>" in message["content"]
                    )
                )
            )
        ]
        for index in removable_indices:
            if running_total <= budget:
                return trimmed, running_total, budget
            role = trimmed[index].get("role", "message")
            trimmed[index]["content"] = (
                f"[content omitted to fit model context window; role={role}]"
            )
            recounted = _count(
                trimmed,
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            if recounted is not None:
                running_total = recounted
        for index in removable_indices:
            if running_total <= budget:
                return trimmed, running_total, budget
            trimmed[index]["content"] = ""
            recounted = _count(
                trimmed,
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            if recounted is not None:
                running_total = recounted
        raise ContextOverflowError(
            f"Request requires {running_total} input tokens but the model budget is "
            f"{budget} (max_input_tokens={max_input_tokens}, output_reserve="
            f"{output_reserve}, safety_margin={safety_margin}, tool_schemas="
            f"{max(0, reserved_tokens)}); protected system or user content cannot "
            "be truncated."
        )

    # Preserve the Auto router's existing aggressive final fallback.
    fallback_indices = [
        index
        for index, message in enumerate(trimmed)
        if message.get("role") != "system"
        and isinstance(message.get("content"), str)
        and message["content"]
    ]
    for index in fallback_indices:
        if running_total <= budget:
            break
        role = trimmed[index].get("role", "message")
        old_tokens = (
            _count(
                [trimmed[index]],
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            or 0
        )
        trimmed[index]["content"] = (
            f"[content omitted to fit model context window; role={role}]"
        )
        running_total += (
            _count(
                [trimmed[index]],
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            or 0
        ) - old_tokens
        recounted = _count(
            trimmed,
            count_tokens,
            estimate_on_failure=estimate_on_count_failure,
        )
        if recounted is not None:
            running_total = recounted

    if running_total > budget:
        for index in fallback_indices:
            if running_total <= budget:
                break
            old_tokens = (
                _count(
                    [trimmed[index]],
                    count_tokens,
                    estimate_on_failure=estimate_on_count_failure,
                )
                or 0
            )
            trimmed[index]["content"] = ""
            running_total += (
                _count(
                    [trimmed[index]],
                    count_tokens,
                    estimate_on_failure=estimate_on_count_failure,
                )
                or 0
            ) - old_tokens
            recounted = _count(
                trimmed,
                count_tokens,
                estimate_on_failure=estimate_on_count_failure,
            )
            if recounted is not None:
                running_total = recounted

    return trimmed, running_total, budget


def admit_langchain_messages(
    messages: list[BaseMessage],
    *,
    sanitize_content: Callable[[Any], Any],
    count_tokens: TokenCounter,
    max_input_tokens: int,
    reserved_tokens: int = 0,
) -> list[BaseMessage]:
    """Admit sanitized LangChain messages without corrupting protected content."""
    provider_messages = convert_langchain_messages(messages, sanitize_content)
    admitted, _, _ = trim_messages_to_fit_context(
        provider_messages,
        count_tokens=count_tokens,
        max_input_tokens=max_input_tokens,
        output_reserve_fraction=0.0,
        minimum_output_reserve=1_024,
        safety_margin_fraction=0.05,
        reserved_tokens=reserved_tokens,
        preserve_protected_content=True,
    )
    if admitted is provider_messages:
        return messages

    result = [message.model_copy(deep=True) for message in messages]
    for index, admitted_message in enumerate(admitted):
        if admitted_message.get("content") != provider_messages[index].get("content"):
            result[index].content = admitted_message["content"]
    return result
