"""Agent setup helpers for orchestrated chat streaming."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any

_PREFLIGHT_TIMEOUT_SEC: float = 2.5
_PREFLIGHT_MAX_TOKENS: int = 1


async def preflight_llm(
    llm: Any,
    *,
    is_provider_rate_limited: Callable[[BaseException], bool],
) -> None:
    """Issue a minimal completion probe to catch immediate provider 429s."""
    from litellm import acompletion

    model = getattr(llm, "model", None)
    if not model or model == "auto":
        return

    try:
        await acompletion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            api_key=getattr(llm, "api_key", None),
            api_base=getattr(llm, "api_base", None),
            max_tokens=_PREFLIGHT_MAX_TOKENS,
            timeout=_PREFLIGHT_TIMEOUT_SEC,
            stream=False,
            metadata={"tags": ["surfsense:internal", "auto-pin-preflight"]},
        )
    except Exception as exc:
        if is_provider_rate_limited(exc):
            raise
        logging.getLogger(__name__).debug(
            "auto_pin_preflight non_rate_limit_error model=%s err=%s",
            model,
            exc,
        )


async def build_main_agent_for_thread(
    agent_factory: Any,
    *,
    llm: Any,
    search_space_id: int,
    db_session: Any,
    connector_service: Any,
    checkpointer: Any,
    user_id: str | None,
    thread_id: int | None,
    agent_config: Any,
    firecrawl_api_key: str | None,
    thread_visibility: Any,
    filesystem_selection: Any,
    disabled_tools: list[str] | None = None,
    mentioned_document_ids: list[int] | None = None,
) -> Any:
    """Run one canonical agent-build call for a single thread."""
    return await agent_factory(
        llm=llm,
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
        checkpointer=checkpointer,
        user_id=user_id,
        thread_id=thread_id,
        agent_config=agent_config,
        firecrawl_api_key=firecrawl_api_key,
        thread_visibility=thread_visibility,
        filesystem_selection=filesystem_selection,
        disabled_tools=disabled_tools,
        mentioned_document_ids=mentioned_document_ids,
    )


async def settle_speculative_agent_build(task: Any) -> None:
    """Wait for a discarded speculative build and swallow its outcome."""
    with contextlib.suppress(BaseException):
        await task


__all__ = [
    "build_main_agent_for_thread",
    "preflight_llm",
    "settle_speculative_agent_build",
]
