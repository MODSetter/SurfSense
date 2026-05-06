"""Top-level chat streaming entrypoints (stubs until wired)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any


async def stream_chat(
    *,
    request: Any,
    user: Any,
    db_session: Any,
) -> AsyncGenerator[str, None]:  # pragma: no cover - orchestrator port in progress
    del request, user, db_session
    raise NotImplementedError(
        "stream_chat: orchestrator not wired yet"
    )
    if False:  # pragma: no cover
        yield ""


async def stream_resume(
    *,
    request: Any,
    user: Any,
    db_session: Any,
) -> AsyncGenerator[str, None]:  # pragma: no cover - orchestrator port in progress
    del request, user, db_session
    raise NotImplementedError(
        "stream_resume: orchestrator not wired yet"
    )
    if False:  # pragma: no cover
        yield ""


async def stream_regenerate(
    *,
    request: Any,
    user: Any,
    db_session: Any,
) -> AsyncGenerator[str, None]:  # pragma: no cover - orchestrator port in progress
    del request, user, db_session
    raise NotImplementedError(
        "stream_regenerate: orchestrator not wired yet"
    )
    if False:  # pragma: no cover
        yield ""
