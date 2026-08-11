"""Auto-continue a final text answer cut off by ``max_tokens``.

``langchain_litellm`` drops ``finish_reason`` from streamed chunks, so a
token-limit cut would otherwise reach the user as a silent stub. When the last
message is a tool-call-free text answer that hit its output cap, re-invoke with
the partial prefilled and stitch the pieces until it finishes. Tool-call
truncation (invalid partial JSON) and non-string content fall back to the
usage-based truncation marker.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.services.token_tracking_service import (
    get_current_accumulator,
    is_output_truncated,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_CONTINUE_NUDGE = HumanMessage(
    content=(
        "Your previous response was cut off before it finished. Continue exactly "
        "where you left off. Do not repeat any text you already wrote and do not "
        "add any preamble."
    )
)


def _final_text_ai(response: Any) -> AIMessage | None:
    result = getattr(response, "result", None) or []
    msg = result[-1] if result else None
    return msg if isinstance(msg, AIMessage) else None


def _plain_text(ai: AIMessage) -> str | None:
    return ai.content if isinstance(ai.content, str) else None


def _output_tokens(ai: AIMessage) -> int:
    return (ai.usage_metadata or {}).get("output_tokens", 0) or 0


def _finish_reason(ai: AIMessage) -> str | None:
    return (ai.response_metadata or {}).get("finish_reason")


def _model_max_tokens(request: Any) -> int | None:
    return getattr(getattr(request, "model", None), "max_tokens", None)


def _continuation_messages(base: list[BaseMessage], accumulated: str) -> list[BaseMessage]:
    return [*base, AIMessage(content=accumulated), _CONTINUE_NUDGE]


def _merge(first_ai: AIMessage, text: str, total_out: int) -> AIMessage:
    usage = dict(first_ai.usage_metadata or {})
    if usage:
        usage["output_tokens"] = total_out
        usage["total_tokens"] = usage.get("input_tokens", 0) + total_out
    metadata = dict(first_ai.response_metadata or {})
    metadata["finish_reason"] = "stop"
    return AIMessage(
        content=text,
        id=first_ai.id,
        usage_metadata=usage or None,
        response_metadata=metadata,
        additional_kwargs=first_ai.additional_kwargs,
    )


class ContinueOnMaxLengthMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Stitch continuations onto a truncated, tool-call-free text answer."""

    def __init__(self, max_continuations: int = 2) -> None:
        super().__init__()
        self.max_continuations = max_continuations

    def _should_continue(self, ai: AIMessage, max_tokens: int | None) -> bool:
        return not ai.tool_calls and is_output_truncated(
            _finish_reason(ai), _output_tokens(ai), max_tokens
        )

    def _finalize(
        self,
        *,
        response: Any,
        last_response: Any,
        first_ai: AIMessage,
        ai: AIMessage | None,
        accumulated: str,
        total_out: int,
        done: int,
        max_tokens: int | None,
    ) -> Any:
        if done == 0:
            return response
        # Recovered a complete answer: the per-call ``length`` the token callback
        # flagged is no longer user-visible, so clear the marker.
        if ai is not None and not self._should_continue(ai, max_tokens):
            acc = get_current_accumulator()
            if acc is not None:
                acc.truncated = False
        return dataclasses.replace(
            last_response, result=[_merge(first_ai, accumulated, total_out)]
        )

    def wrap_model_call(  # type: ignore[override]
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        response = handler(request)
        ai = _final_text_ai(response)
        max_tokens = _model_max_tokens(request)
        if ai is None or (accumulated := _plain_text(ai)) is None:
            return response

        total_out = _output_tokens(ai)
        first_ai, last_response, done = ai, response, 0
        while done < self.max_continuations and self._should_continue(ai, max_tokens):
            done += 1
            last_response = handler(
                request.override(messages=_continuation_messages(request.messages, accumulated))
            )
            ai = _final_text_ai(last_response)
            if ai is None or (piece := _plain_text(ai)) is None:
                break
            accumulated += piece
            total_out += _output_tokens(ai)

        return self._finalize(
            response=response,
            last_response=last_response,
            first_ai=first_ai,
            ai=ai,
            accumulated=accumulated,
            total_out=total_out,
            done=done,
            max_tokens=max_tokens,
        )

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        response = await handler(request)
        ai = _final_text_ai(response)
        max_tokens = _model_max_tokens(request)
        if ai is None or (accumulated := _plain_text(ai)) is None:
            return response

        total_out = _output_tokens(ai)
        first_ai, last_response, done = ai, response, 0
        while done < self.max_continuations and self._should_continue(ai, max_tokens):
            done += 1
            last_response = await handler(
                request.override(messages=_continuation_messages(request.messages, accumulated))
            )
            ai = _final_text_ai(last_response)
            if ai is None or (piece := _plain_text(ai)) is None:
                break
            accumulated += piece
            total_out += _output_tokens(ai)

        return self._finalize(
            response=response,
            last_response=last_response,
            first_ai=first_ai,
            ai=ai,
            accumulated=accumulated,
            total_out=total_out,
            done=done,
            max_tokens=max_tokens,
        )


def build_continue_on_max_length_mw(flags: Any) -> ContinueOnMaxLengthMiddleware | None:
    from ...shared.middleware.flags import enabled

    if not enabled(flags, "enable_continue_on_max_length"):
        return None
    return ContinueOnMaxLengthMiddleware(max_continuations=2)
