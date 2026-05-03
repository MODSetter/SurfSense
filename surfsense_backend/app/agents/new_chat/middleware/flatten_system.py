r"""Coalesce multi-block system messages into a single text block.

Several middlewares in our deepagent stack each call
``append_to_system_message`` on the way down to the model
(``TodoListMiddleware``, ``SurfSenseFilesystemMiddleware``,
``SkillsMiddleware``, ``SubAgentMiddleware`` …). By the time the
request reaches the LLM, the system message has 5+ separate text blocks.

Anthropic enforces a hard cap of **4 ``cache_control`` blocks per
request**, and we configure 2 injection points
(``index: 0`` + ``index: -1``). With ``index: 0`` always targeting
the prepended ``request.system_message``, this middleware is the
defensive partner: it guarantees that "the system block" is *one*
content block, so LiteLLM's ``AnthropicCacheControlHook`` and any
OpenRouter→Anthropic transformer can never multiply our budget into
several breakpoints by spreading ``cache_control`` across multiple
text blocks of a multi-block system content.

Without flattening we used to see::

    OpenrouterException - {"error":{"message":"Provider returned error",
    "code":400,"metadata":{"raw":"...A maximum of 4 blocks with
    cache_control may be provided. Found 5."}}}

(Same error class documented in
https://github.com/BerriAI/litellm/issues/15696 and
https://github.com/BerriAI/litellm/issues/20485 — the litellm-side fix
in PR #15395 covers the litellm transformer but does not protect us
when the OpenRouter SaaS itself does the redistribution.)

A separate fix in :mod:`app.agents.new_chat.prompt_caching` (switching
the first injection point from ``role: system`` to ``index: 0``)
neutralises the *primary* cause of the same 400 — multiple
``SystemMessage``\ s injected by ``before_agent`` middlewares
(priority/tree/memory/file-intent/anonymous-doc) accumulating across
turns, each tagged with ``cache_control`` by the ``role: system``
matcher. This middleware remains useful as defence-in-depth against
the multi-block redistribution path.

Placement: innermost on the system-message-mutation chain, after every
appender (``todo``/``filesystem``/``skills``/``subagents``) and after
summarization, but before ``noop``/``retry``/``fallback`` so each retry
attempt sees a flattened payload. See ``chat_deepagent.py``.

Idempotent: a string-content system message is left untouched. A list
that contains anything other than plain text blocks (e.g. an image) is
also left untouched — those are rare on system messages and we'd lose
the non-text payload by joining.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


def _flatten_text_blocks(content: list[Any]) -> str | None:
    """Return joined text if every block is a plain ``{"type": "text"}``.

    Returns ``None`` when the list contains anything that isn't a text
    block we can safely concatenate (image, audio, file, non-standard
    blocks, dicts with extra non-cache_control fields). The caller
    leaves the original content untouched in that case rather than
    silently dropping payload.

    ``cache_control`` on individual blocks is intentionally discarded —
    the whole point of flattening is to let LiteLLM's
    ``cache_control_injection_points`` re-place a single breakpoint on
    the resulting one-block system content.
    """
    chunks: list[str] = []
    for block in content:
        if isinstance(block, str):
            chunks.append(block)
            continue
        if not isinstance(block, dict):
            return None
        if block.get("type") != "text":
            return None
        text = block.get("text")
        if not isinstance(text, str):
            return None
        chunks.append(text)
    return "\n\n".join(chunks)


def _flattened_request(
    request: ModelRequest[ContextT],
) -> ModelRequest[ContextT] | None:
    """Return a request with system_message flattened, or ``None`` for no-op."""
    sys_msg = request.system_message
    if sys_msg is None:
        return None
    content = sys_msg.content
    if not isinstance(content, list) or len(content) <= 1:
        return None

    flattened = _flatten_text_blocks(content)
    if flattened is None:
        return None

    new_sys = SystemMessage(
        content=flattened,
        additional_kwargs=dict(sys_msg.additional_kwargs),
        response_metadata=dict(sys_msg.response_metadata),
    )
    if sys_msg.id is not None:
        new_sys.id = sys_msg.id
    return request.override(system_message=new_sys)


def _diagnostic_summary(request: ModelRequest[Any]) -> str:
    """One-line dump of cache_control-relevant request shape.

    Temporary diagnostic to prove where the ``Found N`` cache_control
    breakpoints are coming from when Anthropic 400s. Removed once the
    root cause is confirmed and a fix is in place.
    """
    sys_msg = request.system_message
    if sys_msg is None:
        sys_shape = "none"
    elif isinstance(sys_msg.content, str):
        sys_shape = f"str(len={len(sys_msg.content)})"
    elif isinstance(sys_msg.content, list):
        sys_shape = f"list(blocks={len(sys_msg.content)})"
    else:
        sys_shape = f"other({type(sys_msg.content).__name__})"

    role_hist: list[str] = []
    multi_block_msgs = 0
    msgs_with_cc = 0
    sys_msgs_in_history = 0
    for m in request.messages:
        mtype = getattr(m, "type", type(m).__name__)
        role_hist.append(mtype)
        if isinstance(m, SystemMessage):
            sys_msgs_in_history += 1
        c = getattr(m, "content", None)
        if isinstance(c, list):
            multi_block_msgs += 1
            for blk in c:
                if isinstance(blk, dict) and "cache_control" in blk:
                    msgs_with_cc += 1
                    break
        if "cache_control" in getattr(m, "additional_kwargs", {}) or {}:
            msgs_with_cc += 1

    tools = request.tools or []
    tools_with_cc = 0
    for t in tools:
        if isinstance(t, dict) and (
            "cache_control" in t or "cache_control" in t.get("function", {})
        ):
            tools_with_cc += 1

    return (
        f"sys={sys_shape} msgs={len(request.messages)} "
        f"sys_msgs_in_history={sys_msgs_in_history} "
        f"multi_block_msgs={multi_block_msgs} pre_existing_msg_cc={msgs_with_cc} "
        f"tools={len(tools)} pre_existing_tool_cc={tools_with_cc} "
        f"roles={role_hist[-8:]}"
    )


class FlattenSystemMessageMiddleware(
    AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]
):
    """Collapse a multi-text-block system message to a single string.

    Sits innermost on the system-message-mutation chain so it observes
    every middleware's contribution. Has no other side effect — the
    body of every block is preserved, just joined with ``"\\n\\n"``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tools = []

    def wrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> Any:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[flatten_system_diag] %s", _diagnostic_summary(request))
        flattened = _flattened_request(request)
        if flattened is not None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[flatten_system] collapsed %d system blocks to one",
                    len(request.system_message.content),  # type: ignore[arg-type, union-attr]
                )
            return handler(flattened)
        return handler(request)

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> Any:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[flatten_system_diag] %s", _diagnostic_summary(request))
        flattened = _flattened_request(request)
        if flattened is not None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "[flatten_system] collapsed %d system blocks to one",
                    len(request.system_message.content),  # type: ignore[arg-type, union-attr]
                )
            return await handler(flattened)
        return await handler(request)


__all__ = [
    "FlattenSystemMessageMiddleware",
    "_flatten_text_blocks",
    "_flattened_request",
]
