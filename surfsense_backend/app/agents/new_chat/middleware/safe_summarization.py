"""Safe wrapper around deepagents' SummarizationMiddleware.

Upstream issue
--------------
`deepagents.middleware.summarization.SummarizationMiddleware._aoffload_to_backend`
(and its sync counterpart) call
``get_buffer_string(filtered_messages)`` before writing the evicted history
to the backend file. In recent ``langchain-core`` versions, ``get_buffer_string``
accesses ``m.text`` which iterates ``self.content`` — this raises
``TypeError: 'NoneType' object is not iterable`` whenever an ``AIMessage``
has ``content=None`` (common when a model returns *only* tool_calls, seen
frequently with Azure OpenAI ``gpt-5.x`` responses streamed through
LiteLLM).

The exception aborts the whole agent turn, so the user just sees "Error during
chat" with no assistant response.

Fix
---
We subclass ``SummarizationMiddleware`` and override
``_filter_summary_messages`` — the only call site that feeds messages into
``get_buffer_string`` — to return *copies* of messages whose ``content`` is
``None`` with ``content=""``. The originals flowing through the rest of the
agent state are untouched.

We also expose a drop-in ``create_safe_summarization_middleware`` factory
that mirrors ``deepagents.middleware.summarization.create_summarization_middleware``
but instantiates our safe subclass.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    compute_summarization_defaults,
)

if TYPE_CHECKING:
    from deepagents.backends.protocol import BACKEND_TYPES
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AnyMessage

logger = logging.getLogger(__name__)


def _sanitize_message_content(msg: "AnyMessage") -> "AnyMessage":
    """Return ``msg`` with ``content`` coerced to a non-``None`` value.

    ``get_buffer_string`` reads ``m.text`` which iterates ``self.content``;
    when a provider streams back an ``AIMessage`` with only tool_calls and
    no text, ``content`` can be ``None`` and the iteration explodes. We
    replace ``None`` with an empty string so downstream consumers that only
    care about text see an empty body.

    The original message is left untouched — we return a copy via
    pydantic's ``model_copy`` when available, otherwise we fall back to
    re-setting the attribute on a shallow copy.
    """

    if getattr(msg, "content", "not-missing") is not None:
        return msg

    try:
        return msg.model_copy(update={"content": ""})
    except AttributeError:
        import copy

        new_msg = copy.copy(msg)
        try:
            new_msg.content = ""
        except Exception:  # pragma: no cover - defensive
            logger.debug(
                "Could not sanitize content=None on message of type %s",
                type(msg).__name__,
            )
            return msg
        return new_msg


class SafeSummarizationMiddleware(SummarizationMiddleware):
    """`SummarizationMiddleware` that tolerates messages with ``content=None``.

    Only ``_filter_summary_messages`` is overridden — this is the single
    helper invoked by both the sync and async offload paths immediately
    before ``get_buffer_string``. Normalising here means we get coverage
    for both without having to copy the (long, rapidly-changing) offload
    implementations from upstream.
    """

    def _filter_summary_messages(
        self, messages: "list[AnyMessage]"
    ) -> "list[AnyMessage]":
        filtered = super()._filter_summary_messages(messages)
        return [_sanitize_message_content(m) for m in filtered]


def create_safe_summarization_middleware(
    model: "BaseChatModel",
    backend: "BACKEND_TYPES",
) -> SafeSummarizationMiddleware:
    """Drop-in replacement for ``create_summarization_middleware``.

    Mirrors the defaults computed by ``deepagents`` but returns our
    ``SafeSummarizationMiddleware`` subclass so the
    ``content=None`` crash in ``get_buffer_string`` is avoided.
    """

    defaults = compute_summarization_defaults(model)
    return SafeSummarizationMiddleware(
        model=model,
        backend=backend,
        trigger=defaults["trigger"],
        keep=defaults["keep"],
        trim_tokens_to_summarize=None,
        truncate_args_settings=defaults["truncate_args_settings"],
    )


__all__ = [
    "SafeSummarizationMiddleware",
    "create_safe_summarization_middleware",
]
