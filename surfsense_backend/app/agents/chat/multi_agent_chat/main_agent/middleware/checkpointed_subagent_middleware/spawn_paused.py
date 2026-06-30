"""Per-workspace spawn-paused kill switch for the ``task`` boundary.

When operators see a runaway loop, a vendor outage, or a billing event
that requires immediate cessation of subagent traffic for a specific
workspace, they flip a Redis flag and the ``task`` tool short-circuits
without touching downstream services. The flag is **per-workspace**
so one tenant's incident never silences the rest of the deployment.

Flag key:    ``surfsense:spawn_paused:{workspace_id}``
Flag value:  any string-truthy value (we read presence, not contents).
TTL:         set by whoever toggles the flag — this module never expires
             keys on its own, since "the flag is on" is itself the signal
             that a human (or alert) needs to investigate.

The check is best-effort: Redis errors are logged but do not block the
``task`` invocation. Failing closed (block-on-redis-error) would let a
single Redis blip take the whole orchestrator offline; failing open
preserves availability and the alarm bells (rate-limits, cost spikes)
will surface the underlying outage.
"""

from __future__ import annotations

import contextlib
import logging
import os

from app.config import config

logger = logging.getLogger(__name__)


# Operators can disable the check entirely (e.g. local dev without Redis)
# by setting ``SURFSENSE_TASK_SPAWN_PAUSED_DISABLED=1``. Default is
# enabled so production never relies on flipping an opt-out flag.
_DISABLED = os.environ.get(
    "SURFSENSE_TASK_SPAWN_PAUSED_DISABLED", ""
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _flag_key(workspace_id: int) -> str:
    return f"surfsense:spawn_paused:{workspace_id}"


async def is_spawn_paused(workspace_id: int | None) -> bool:
    """Return ``True`` iff the workspace's spawn-paused flag is set in Redis.

    A ``None`` workspace (e.g. dev paths that did not plumb the id
    through yet) bypasses the check. So does a Redis outage — see module
    docstring for the fail-open rationale.
    """
    if _DISABLED or workspace_id is None:
        return False
    try:
        # Local import keeps the cold-path import cheap and lets routes
        # that never call ``task`` skip the redis dependency entirely.
        import redis.asyncio as aioredis  # type: ignore[import-not-found]

        client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        try:
            raw = await client.get(_flag_key(workspace_id))
        finally:
            # ``aclose()`` is the async-safe variant on redis-py >=5; fall back
            # to ``close()`` for older clients pinned in tests.
            close = getattr(client, "aclose", None) or getattr(client, "close", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    await close()  # type: ignore[misc]
        return bool(raw)
    except Exception:
        logger.warning(
            "spawn_paused check failed for workspace_id=%s; failing open.",
            workspace_id,
            exc_info=True,
        )
        return False


__all__ = ["is_spawn_paused"]
