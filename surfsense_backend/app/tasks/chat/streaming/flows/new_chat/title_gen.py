"""Background thread-title generation (first-response only).

The first assistant response in a thread gets a short auto-generated title
inserted into ``new_chat_threads.title``. We:

  1. Spawn the generation as an ``asyncio.Task`` so it runs in parallel with
     the agent stream (no extra TTFT).
  2. Probe inside the task (on its own shielded session) whether this is
     actually the first response — newer turns short-circuit to ``None``.
  3. Inject the resulting ``thread-title-update`` SSE frame on the first agent
     event after the task completes (mid-stream interlock), or right before
     the finish frames (post-stream join) if the task hadn't finished yet.

Usage tokens come directly off the response (LiteLLM's async callback fires
via fire-and-forget ``create_task``, so the ``TokenTrackingCallback`` would
run too late). We also blank the per-task accumulator so the late callback
doesn't double-count.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.future import select

from app.db import NewChatMessage, NewChatThread, shielded_async_session
from app.prompts import TITLE_GENERATION_PROMPT
from app.services.new_streaming_service import VercelStreamingService

if TYPE_CHECKING:
    from app.agents.new_chat.llm_config import AgentConfig
    from app.services.token_tracking_service import TokenAccumulator


logger = logging.getLogger(__name__)


def spawn_title_task(
    *,
    chat_id: int,
    user_query: str,
    user_image_data_urls: list[str] | None,
    assistant_message_id: int | None,
    llm: Any,
    agent_config: AgentConfig | None,
) -> asyncio.Task[tuple[str | None, dict | None]] | None:
    """Spawn ``_generate_title``; returns ``None`` when prerequisites aren't met.

    Title gen is gated on a real ``assistant_message_id`` so a stream that
    aborts before persistence can never leave a thread with a title and no
    anchoring rows.
    """
    if assistant_message_id is None:
        return None
    return asyncio.create_task(
        _generate_title(
            chat_id=chat_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            assistant_message_id=assistant_message_id,
            llm=llm,
            agent_config=agent_config,
        )
    )


async def _generate_title(
    *,
    chat_id: int,
    user_query: str,
    user_image_data_urls: list[str] | None,
    assistant_message_id: int,
    llm: Any,
    agent_config: AgentConfig | None,
) -> tuple[str | None, dict | None]:
    """Probe is-first-response, then call ``acompletion``. Returns ``(title, usage)``."""
    try:
        from litellm import acompletion

        from app.services.llm_router_service import LLMRouterService
        from app.services.provider_api_base import resolve_api_base
        from app.services.token_tracking_service import _turn_accumulator

        # Excludes this turn's own assistant row (pre-written by
        # ``persist_assistant_shell``) — without the ``!=`` filter the gate
        # would false-negative on every turn after the first.
        try:
            async with shielded_async_session() as probe_session:
                probe_result = await probe_session.execute(
                    select(NewChatMessage.id)
                    .filter(
                        NewChatMessage.thread_id == chat_id,
                        NewChatMessage.role == "assistant",
                        NewChatMessage.id != assistant_message_id,
                    )
                    .limit(1)
                )
                is_first_response = probe_result.scalars().first() is None
        except Exception:
            logger.warning(
                "[TitleGen] first-response probe failed (chat_id=%s)",
                chat_id,
                exc_info=True,
            )
            return None, None

        if not is_first_response:
            return None, None

        _turn_accumulator.set(None)

        title_seed = user_query.strip() or (
            f"[{len(user_image_data_urls or [])} image(s)]"
            if user_image_data_urls
            else ""
        )
        prompt = TITLE_GENERATION_PROMPT.replace(
            "{user_query}", title_seed[:500] or "(message)"
        )
        messages = [{"role": "user", "content": prompt}]

        if getattr(llm, "model", None) == "auto":
            router = LLMRouterService.get_router()
            response = await router.acompletion(model="auto", messages=messages)
        else:
            # Apply the same ``api_base`` cascade chat / vision / image-gen
            # call sites use so we never inherit ``litellm.api_base``
            # (commonly set by ``AZURE_OPENAI_ENDPOINT``) when the chat
            # config itself ships an empty ``api_base``. Without this the
            # title-gen on an OpenRouter chat config would 404 against the
            # inherited Azure endpoint — see ``provider_api_base`` for the
            # same bug repro on the image-gen / vision paths.
            raw_model = getattr(llm, "model", "") or ""
            provider_prefix = raw_model.split("/", 1)[0] if "/" in raw_model else None
            provider_value = agent_config.provider if agent_config is not None else None
            title_api_base = resolve_api_base(
                provider=provider_value,
                provider_prefix=provider_prefix,
                config_api_base=getattr(llm, "api_base", None),
            )
            response = await acompletion(
                model=raw_model,
                messages=messages,
                api_key=getattr(llm, "api_key", None),
                api_base=title_api_base,
            )

        usage_info = None
        usage = getattr(response, "usage", None)
        if usage:
            raw_model = getattr(llm, "model", "") or ""
            model_name = (
                raw_model.split("/", 1)[-1]
                if "/" in raw_model
                else (raw_model or response.model or "unknown")
            )
            usage_info = {
                "model": model_name,
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }

        raw_title = response.choices[0].message.content.strip()
        if raw_title and len(raw_title) <= 100:
            return raw_title.strip("\"'"), usage_info
        return None, usage_info
    except Exception:
        logger.exception("[TitleGen] _generate_title failed")
        return None, None


async def maybe_emit_title_update(
    *,
    title_task: asyncio.Task[tuple[str | None, dict | None]] | None,
    title_emitted: bool,
    chat_id: int,
    accumulator: TokenAccumulator,
    streaming_service: VercelStreamingService,
):
    """Inject one ``thread-title-update`` SSE if the task completed.

    Yields the SSE frame (when applicable). Returns nothing; the orchestrator
    flips ``title_emitted`` itself after iterating so we don't fight Python's
    nonlocal-in-generator semantics.
    """
    if title_task is None or title_emitted or not title_task.done():
        return
    generated_title, title_usage = title_task.result()
    if title_usage:
        accumulator.add(**title_usage)
    if generated_title:
        async with shielded_async_session() as title_session:
            title_thread_result = await title_session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            title_thread = title_thread_result.scalars().first()
            if title_thread:
                title_thread.title = generated_title
                await title_session.commit()
        yield streaming_service.format_thread_title_update(chat_id, generated_title)


async def await_pending_title_update(
    *,
    title_task: asyncio.Task[tuple[str | None, dict | None]] | None,
    title_emitted: bool,
    chat_id: int,
    accumulator: TokenAccumulator,
    streaming_service: VercelStreamingService,
):
    """If the task hadn't completed during the stream, await it now and emit.

    Used right before the finish frames in the success path. Mirror of
    ``maybe_emit_title_update`` but unconditionally awaits.
    """
    if title_task is None or title_emitted:
        return
    generated_title, title_usage = await title_task
    if title_usage:
        accumulator.add(**title_usage)
    if generated_title:
        async with shielded_async_session() as title_session:
            title_thread_result = await title_session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            title_thread = title_thread_result.scalars().first()
            if title_thread:
                title_thread.title = generated_title
                await title_session.commit()
        yield streaming_service.format_thread_title_update(chat_id, generated_title)
