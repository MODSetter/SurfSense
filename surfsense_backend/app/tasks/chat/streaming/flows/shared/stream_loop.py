"""Drive ``stream_agent_events`` with in-stream rate-limit recovery.

Both ``stream_new_chat`` and ``stream_resume_chat`` wrap the agent event loop
in a ``while True`` that catches the *first* provider rate-limit error
(``can_runtime_recover``) before any SSE event reaches the user, rebuilds the
agent on an alternative auto-pin, and retries the turn.

The recovery callback is flow-specific (different ``mentioned_document_ids``
contract, different logging label, etc.) — this module owns the loop shape,
the caller owns the rebuild.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.agent.event_loop import stream_agent_events
from app.tasks.chat.streaming.shared.stream_result import StreamResult

# Returns the rebuilt agent on a successful recovery, or ``None`` to re-raise
# the original exception (and let the orchestrator's terminal-error path
# handle it).
RecoverFn = Callable[[BaseException, bool], Awaitable[Any | None]]


async def run_stream_loop(
    *,
    agent: Any,
    streaming_service: VercelStreamingService,
    config: dict[str, Any],
    input_data: Any,
    stream_result: StreamResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
    fallback_commit_search_space_id: int | None,
    fallback_commit_created_by_id: str | None,
    fallback_commit_filesystem_mode: FilesystemMode,
    fallback_commit_thread_id: int | None,
    runtime_context: Any,
    content_builder: Any | None,
    recover: RecoverFn,
    on_first_event: Callable[[], None] | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames; rebuild and retry once on a pre-first-event rate limit.

    ``on_first_event`` fires after the first frame is observed (used by both
    flows to write a one-time ``First agent event in N.NNNs`` perf line).
    """
    first_event_logged = False
    while True:
        try:
            async for sse in stream_agent_events(
                agent=agent,
                config=config,
                input_data=input_data,
                streaming_service=streaming_service,
                result=stream_result,
                step_prefix=step_prefix,
                initial_step_id=initial_step_id,
                initial_step_title=initial_step_title,
                initial_step_items=initial_step_items,
                fallback_commit_search_space_id=fallback_commit_search_space_id,
                fallback_commit_created_by_id=fallback_commit_created_by_id,
                fallback_commit_filesystem_mode=fallback_commit_filesystem_mode,
                fallback_commit_thread_id=fallback_commit_thread_id,
                runtime_context=runtime_context,
                content_builder=content_builder,
            ):
                if not first_event_logged:
                    if on_first_event is not None:
                        on_first_event()
                    first_event_logged = True
                yield sse
            return
        except Exception as exc:
            new_agent = await recover(exc, first_event_logged)
            if new_agent is None:
                raise
            agent = new_agent
            continue
