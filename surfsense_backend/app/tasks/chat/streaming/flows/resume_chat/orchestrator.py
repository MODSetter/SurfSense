"""``stream_resume_chat`` — public entry point for a HITL resume turn.

Slim composition layer over the per-concern modules in this folder and the
building blocks under ``flows/shared/``. Mirrors ``stream_new_chat`` but:

  * No user-message persistence (the original turn already wrote it).
  * No mentions / surfsense-doc / report context assembly (seeded by original).
  * No title generation (only fires on first-response).
  * Synchronous ``persist_assistant_shell`` call (we have no other in-flight
    pre-stream work to overlap it with).
  * ``input_data`` is a ``Command(resume=lg_resume_map)`` instead of a
    LangChain message list.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import AsyncGenerator
from functools import partial
from uuid import UUID

import anyio

from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import end_turn
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
)
from app.db import ChatVisibility, async_session_maker
from app.observability import otel as ot
from app.services.chat_session_state_service import set_ai_responding
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.agent.builder import build_main_agent_for_thread
from app.tasks.chat.streaming.contract.file_contract import log_file_contract
from app.tasks.chat.streaming.errors.emitter import emit_stream_terminal_error
from app.tasks.chat.streaming.flows.resume_chat.assistant_shell import (
    persist_resume_assistant_shell,
)
from app.tasks.chat.streaming.flows.resume_chat.resume_routing import (
    build_resume_routing,
)
from app.tasks.chat.streaming.flows.resume_chat.runtime_context import (
    build_resume_chat_runtime_context,
)
from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
    finalize_assistant_message,
)
from app.tasks.chat.streaming.flows.shared.finalize_emit import iter_token_usage_frame
from app.tasks.chat.streaming.flows.shared.finally_cleanup import (
    close_session_and_clear_ai_responding,
    run_gc_pass,
)
from app.tasks.chat.streaming.flows.shared.first_frames import (
    iter_final_frames,
    iter_initial_frames,
)
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.pre_stream_setup import (
    get_chat_checkpointer,
    setup_connector_and_firecrawl,
)
from app.tasks.chat.streaming.flows.shared.premium_quota import (
    CreditReservation,
    finalize_credit,
    needs_credit_quota,
    release_credit,
    reserve_credit,
)
from app.tasks.chat.streaming.flows.shared.rate_limit_recovery import (
    can_recover_provider_rate_limit,
    log_rate_limit_recovered,
    reroute_to_next_auto_pin,
)
from app.tasks.chat.streaming.flows.shared.span import (
    close_chat_request_span,
    open_chat_request_span,
    set_agent_mode,
)
from app.tasks.chat.streaming.flows.shared.stream_loop import run_stream_loop
from app.tasks.chat.streaming.flows.shared.terminal_error import (
    handle_terminal_exception,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.tasks.chat.streaming.shared.utils import resume_step_prefix
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


async def stream_resume_chat(
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    disabled_tools: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Resume a paused HITL turn with the user's decisions.

    Mirrors ``stream_new_chat`` except for the resume-specific routing of
    ``decisions`` to per-``tool_call_id`` slices (``build_resume_routing``).
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()
    fs_mode = filesystem_selection.mode.value if filesystem_selection else "cloud"
    fs_platform = (
        filesystem_selection.client_platform.value if filesystem_selection else "web"
    )
    stream_result.request_id = request_id
    stream_result.turn_id = f"{chat_id}:{int(time.time() * 1000)}"
    stream_result.filesystem_mode = fs_mode
    stream_result.client_platform = fs_platform

    chat_agent_mode = "unknown"
    chat_outcome = "success"
    chat_error_category: str | None = None
    chat_span_cm, chat_span = open_chat_request_span(
        chat_id=chat_id,
        search_space_id=search_space_id,
        flow="resume",
        request_id=request_id,
        turn_id=stream_result.turn_id,
        filesystem_mode=fs_mode,
        client_platform=fs_platform,
        agent_mode=chat_agent_mode,
    )
    log_file_contract("turn_start", stream_result)
    _perf_log.info(
        "[stream_resume] filesystem_mode=%s client_platform=%s",
        fs_mode,
        fs_platform,
    )

    from app.services.token_tracking_service import start_turn

    accumulator = start_turn()

    premium_reservation: CreditReservation | None = None
    busy_error_raised = False

    emit_stream_error = partial(
        emit_stream_terminal_error,
        streaming_service=streaming_service,
        flow="resume",
        request_id=request_id,
        thread_id=chat_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    session = async_session_maker()
    try:
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))

        requested_llm_config_id = llm_config_id

        # --- LLM config ---

        _t0 = time.perf_counter()
        try:
            from app.services.auto_model_pin_service import (
                resolve_or_get_pinned_llm_config_id,
            )

            pinned = await resolve_or_get_pinned_llm_config_id(
                session,
                thread_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                selected_llm_config_id=llm_config_id,
            )
            llm_config_id = pinned.resolved_llm_config_id
            ot.add_event(
                "model.pin.resolved",
                {
                    "pin.requested_id": requested_llm_config_id,
                    "pin.resolved_id": llm_config_id,
                    "pin.requires_image_input": False,
                },
            )
        except ValueError as pin_error:
            yield emit_stream_error(
                message=str(pin_error),
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        llm, agent_config, llm_load_error = await load_llm_bundle(
            session, config_id=llm_config_id, search_space_id=search_space_id
        )
        if llm_load_error:
            yield emit_stream_error(
                message=llm_load_error,
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return
        _perf_log.info(
            "[stream_resume] LLM config loaded in %.3fs", time.perf_counter() - _t0
        )

        if needs_credit_quota(agent_config, user_id):
            premium_reservation = await reserve_credit(
                agent_config=agent_config,
                user_id=user_id,  # type: ignore[arg-type]
            )
            if not premium_reservation.allowed:
                ot.add_event("quota.denied", {"quota.code": "PREMIUM_QUOTA_EXHAUSTED"})
                if requested_llm_config_id == 0:
                    try:
                        pinned_fb = await resolve_or_get_pinned_llm_config_id(
                            session,
                            thread_id=chat_id,
                            search_space_id=search_space_id,
                            user_id=user_id,
                            selected_llm_config_id=0,
                            force_repin_free=True,
                        )
                        llm_config_id = pinned_fb.resolved_llm_config_id
                        ot.add_event(
                            "model.repin",
                            {
                                "repin.reason": "premium_quota_exhausted",
                                "repin.to_config_id": llm_config_id,
                            },
                        )
                    except ValueError as pin_error:
                        yield emit_stream_error(
                            message=str(pin_error),
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return
                    llm, agent_config, llm_load_error = await load_llm_bundle(
                        session,
                        config_id=llm_config_id,
                        search_space_id=search_space_id,
                    )
                    if llm_load_error:
                        yield emit_stream_error(
                            message=llm_load_error,
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        )
                        yield streaming_service.format_done()
                        return
                    premium_reservation = None
                    from app.tasks.chat.streaming.errors.classifier import (
                        log_chat_stream_error,
                    )

                    log_chat_stream_error(
                        flow="resume",
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        request_id=request_id,
                        thread_id=chat_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        message=(
                            "Premium quota exhausted on pinned model; "
                            "auto-fallback switched to a free model"
                        ),
                        extra={
                            "fallback_config_id": llm_config_id,
                            "auto_fallback": True,
                        },
                    )
                else:
                    yield emit_stream_error(
                        message=(
                            "Buy more credits to continue with this model, or "
                            "switch to a free model"
                        ),
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        extra={
                            "resolved_config_id": llm_config_id,
                            "auto_fallback": False,
                        },
                    )
                    yield streaming_service.format_done()
                    return

        if not llm:
            yield emit_stream_error(
                message="Failed to create LLM instance",
                error_kind="server_error",
                error_code="SERVER_ERROR",
            )
            yield streaming_service.format_done()
            return

        # --- Pre-stream setup ---

        _t0 = time.perf_counter()
        connector_service, firecrawl_api_key = await setup_connector_and_firecrawl(
            session, search_space_id=search_space_id
        )
        _perf_log.info(
            "[stream_resume] Connector service + firecrawl key in %.3fs",
            time.perf_counter() - _t0,
        )

        _t0 = time.perf_counter()
        checkpointer = await get_chat_checkpointer()
        _perf_log.info(
            "[stream_resume] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE
        chat_agent_mode = "multi"
        set_agent_mode(chat_span, chat_agent_mode)

        _t0 = time.perf_counter()
        agent_factory = create_multi_agent_chat_deep_agent
        agent = await build_main_agent_for_thread(
            agent_factory,
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            filesystem_selection=filesystem_selection,
            disabled_tools=disabled_tools,
        )
        _perf_log.info(
            "[stream_resume] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # Release the transaction before streaming (same rationale as stream_new_chat).
        await session.commit()
        session.expunge_all()

        _perf_log.info(
            "[stream_resume] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        # --- Resume routing ---

        from langgraph.types import Command

        routing = await build_resume_routing(
            agent, chat_id=chat_id, decisions=decisions
        )

        config = {
            "configurable": {
                "thread_id": str(chat_id),
                "request_id": request_id or "unknown",
                "turn_id": stream_result.turn_id,
                # Per-``tool_call_id`` resume slices read by
                # ``SurfSenseCheckpointedSubAgentMiddleware``. Parallel
                # siblings each pop their own entry, so they never race.
                "surfsense_resume_value": routing.routed_resume_value,
            },
            # Same rationale as ``stream_new_chat``: effectively uncapped to
            # mirror the agent default and OpenCode's session loop. Doom-loop
            # / call-limit middleware enforce the real ceiling.
            "recursion_limit": 10_000,
        }

        # --- First SSE frames ---

        for sse in iter_initial_frames(
            streaming_service, turn_id=stream_result.turn_id
        ):
            yield sse

        # --- Assistant-shell persistence + id frame ---

        assistant_message_id = await persist_resume_assistant_shell(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=stream_result.turn_id,
        )
        if assistant_message_id is None:
            yield emit_stream_error(
                message=(
                    "We couldn't initialize the assistant message. Please try again."
                ),
                error_kind="server_error",
                error_code="MESSAGE_PERSIST_FAILED",
            )
            for sse in iter_final_frames(streaming_service):
                yield sse
            return

        yield streaming_service.format_data(
            "assistant-message-id",
            {"message_id": assistant_message_id, "turn_id": stream_result.turn_id},
        )

        stream_result.assistant_message_id = assistant_message_id
        stream_result.content_builder = AssistantContentBuilder()

        runtime_context = build_resume_chat_runtime_context(
            search_space_id=search_space_id,
            request_id=request_id,
            turn_id=stream_result.turn_id,
        )

        # --- Stream loop ---

        _t_stream_start = time.perf_counter()
        runtime_rate_limit_recovered = False

        def _on_first_event() -> None:
            _perf_log.info(
                "[stream_resume] First agent event in %.3fs (stream), %.3fs (total) (chat_id=%s)",
                time.perf_counter() - _t_stream_start,
                time.perf_counter() - _t_total,
                chat_id,
            )

        async def _recover(exc: BaseException, first_event_seen: bool):
            nonlocal llm_config_id, llm, agent_config, runtime_rate_limit_recovered
            if not can_recover_provider_rate_limit(
                exc,
                first_event_seen=first_event_seen,
                runtime_rate_limit_recovered=runtime_rate_limit_recovered,
                requested_llm_config_id=requested_llm_config_id,
                current_llm_config_id=llm_config_id,
            ):
                return None
            runtime_rate_limit_recovered = True
            previous_config_id = llm_config_id
            llm_config_id = await reroute_to_next_auto_pin(
                session,
                chat_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                current_llm_config_id=llm_config_id,
                requires_image_input=False,
            )
            new_llm, new_agent_config, llm_load_err = await load_llm_bundle(
                session, config_id=llm_config_id, search_space_id=search_space_id
            )
            if llm_load_err:
                return None
            llm = new_llm
            agent_config = new_agent_config

            _t_rebuild = time.perf_counter()
            new_agent = await build_main_agent_for_thread(
                agent_factory,
                llm=llm,
                search_space_id=search_space_id,
                db_session=session,
                connector_service=connector_service,
                checkpointer=checkpointer,
                user_id=user_id,
                thread_id=chat_id,
                agent_config=agent_config,
                firecrawl_api_key=firecrawl_api_key,
                thread_visibility=visibility,
                filesystem_selection=filesystem_selection,
                disabled_tools=disabled_tools,
            )
            _perf_log.info(
                "[stream_resume] Runtime rate-limit recovery repinned "
                "config_id=%s -> %s and rebuilt agent in %.3fs",
                previous_config_id,
                llm_config_id,
                time.perf_counter() - _t_rebuild,
            )
            log_rate_limit_recovered(
                flow="resume",
                request_id=request_id,
                chat_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                previous_config_id=previous_config_id,
                new_config_id=llm_config_id,
            )
            return new_agent

        async for sse in run_stream_loop(
            agent=agent,
            streaming_service=streaming_service,
            config=config,
            input_data=Command(resume=routing.lg_resume_map),
            stream_result=stream_result,
            step_prefix=resume_step_prefix(stream_result.turn_id),
            fallback_commit_search_space_id=search_space_id,
            fallback_commit_created_by_id=user_id,
            fallback_commit_filesystem_mode=(
                filesystem_selection.mode
                if filesystem_selection
                else FilesystemMode.CLOUD
            ),
            fallback_commit_thread_id=chat_id,
            runtime_context=runtime_context,
            content_builder=stream_result.content_builder,
            recover=_recover,
            on_first_event=_on_first_event,
        ):
            yield sse

        _perf_log.info(
            "[stream_resume] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )

        # --- Finalize ---

        if stream_result.is_interrupted:
            ot.add_event("chat.interrupted", {"chat.flow": "resume"})
            for sse in iter_token_usage_frame(
                streaming_service,
                accumulator=accumulator,
                log_label="interrupted resume_chat",
            ):
                yield sse
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        if premium_reservation is not None and user_id:
            await finalize_credit(
                reservation=premium_reservation,
                user_id=user_id,
                accumulator=accumulator,
            )
            premium_reservation = None

        for sse in iter_token_usage_frame(
            streaming_service, accumulator=accumulator, log_label="normal resume_chat"
        ):
            yield sse

        for sse in iter_final_frames(streaming_service):
            yield sse

    except Exception as exc:
        frames, summary = handle_terminal_exception(
            exc,
            flow="resume",
            flow_label="resume",
            log_prefix="stream_resume_chat",
            streaming_service=streaming_service,
            request_id=request_id,
            chat_id=chat_id,
            search_space_id=search_space_id,
            user_id=user_id,
            chat_span=chat_span,
        )
        if summary["busy_error_raised"]:
            busy_error_raised = True
        chat_outcome = summary["chat_outcome"]
        chat_error_category = summary["chat_error_category"]
        for sse in frames:
            yield sse

    finally:
        with anyio.CancelScope(shield=True):
            end_turn(str(chat_id))

            if premium_reservation is not None and user_id:
                await release_credit(reservation=premium_reservation, user_id=user_id)

            await close_session_and_clear_ai_responding(session, chat_id)

            await finalize_assistant_message(
                stream_result=stream_result,
                chat_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                accumulator=accumulator,
                log_prefix="stream_resume",
            )

        # Release the lock from the original interrupted turn or any
        # re-interrupt/bailout. Skip on ``BusyError`` (lock not held here).
        if not busy_error_raised:
            with contextlib.suppress(Exception):
                end_turn(str(chat_id))
                _perf_log.info("[stream_resume] end_turn cleanup (chat_id=%s)", chat_id)

        agent = llm = connector_service = None
        stream_result = None
        session = None

        run_gc_pass(log_prefix="stream_resume", chat_id=chat_id)
        close_chat_request_span(
            span_cm=chat_span_cm,
            span=chat_span,
            chat_outcome=chat_outcome,
            chat_agent_mode=chat_agent_mode,
            flow="resume",
            chat_error_category=chat_error_category,
            duration_seconds=time.perf_counter() - _t_total,
        )
