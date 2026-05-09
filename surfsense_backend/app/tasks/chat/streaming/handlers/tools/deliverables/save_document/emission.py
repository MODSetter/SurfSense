"""save_document: default completion card and terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.default import emission as _default
from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    yield from _default.iter_completion_emission_frames(ctx)
