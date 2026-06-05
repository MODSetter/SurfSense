"""Build the per-invocation ``SurfSenseContextSchema`` for a resume turn.

Resume doesn't carry new ``mentioned_document_ids`` (those are seeded by the
original turn). We still build the context so future middleware extensions
can rely on ``runtime.context`` always being populated.
"""

from __future__ import annotations

from app.agents.chat.shared.context import SurfSenseContextSchema


def build_resume_chat_runtime_context(
    *,
    search_space_id: int,
    request_id: str | None,
    turn_id: str,
) -> SurfSenseContextSchema:
    return SurfSenseContextSchema(
        search_space_id=search_space_id,
        request_id=request_id,
        turn_id=turn_id,
    )
