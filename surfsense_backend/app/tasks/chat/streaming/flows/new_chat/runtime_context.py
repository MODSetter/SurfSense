"""Build the per-invocation ``SurfSenseContextSchema`` for a new-chat turn.

Carries the per-turn read inputs that middlewares read via
``runtime.context.*`` instead of from their ``__init__`` closures, so the same
compiled-agent instance can serve multiple turns with different
mention lists / request ids / turn ids without rebuilding the graph.
"""

from __future__ import annotations

from app.agents.new_chat.context import SurfSenseContextSchema


def build_new_chat_runtime_context(
    *,
    search_space_id: int,
    mentioned_document_ids: list[int] | None,
    accepted_folder_ids: list[int],
    mentioned_folder_ids: list[int] | None,
    request_id: str | None,
    turn_id: str,
) -> SurfSenseContextSchema:
    """``mentioned_document_ids`` is consumed by ``KnowledgePriorityMiddleware``.

    ``accepted_folder_ids`` (post-resolve) wins over the raw
    ``mentioned_folder_ids`` from the request: the resolver drops chips that
    pointed at deleted folders or folders the caller can't see, so middlewares
    only get authorized ids.
    """
    return SurfSenseContextSchema(
        search_space_id=search_space_id,
        mentioned_document_ids=list(mentioned_document_ids or []),
        mentioned_folder_ids=list(
            accepted_folder_ids or mentioned_folder_ids or []
        ),
        request_id=request_id,
        turn_id=turn_id,
    )
