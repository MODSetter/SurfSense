"""Multi-agent v1 entrypoint scaffold with safe fallback behavior."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any


class MultiAgentEntrypoint:
    def stream_new_chat(
        self,
        *,
        fallback_streamer: Callable[..., AsyncGenerator[str, None]],
        fallback_kwargs: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        return fallback_streamer(**fallback_kwargs)

    def stream_resume_chat(
        self,
        *,
        fallback_streamer: Callable[..., AsyncGenerator[str, None]],
        fallback_kwargs: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        return fallback_streamer(**fallback_kwargs)
