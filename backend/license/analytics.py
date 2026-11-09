"""PostHog for the license portal's personless events: a silent no-op without POSTHOG_API_KEY.

The client queues onto its own thread, so a capture never waits on the network;
`shutdown()` flushes it before a script exits.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from license.settings import config

logger = logging.getLogger(__name__)

_client: Any | None = None
_init_attempted = False
_lock = threading.Lock()

# The source surfsense_backend stamped, so the funnel's PostHog queries keep matching.
_SOURCE = "backend"


def _get_client() -> Any | None:
    global _client, _init_attempted
    if _init_attempted:
        return _client
    with _lock:
        if _init_attempted:
            return _client
        _init_attempted = True
        if not config.POSTHOG_API_KEY:
            return None
        try:
            from posthog import Posthog

            _client = Posthog(
                project_api_key=config.POSTHOG_API_KEY, host=config.POSTHOG_HOST
            )
        except Exception:
            logger.warning("PostHog analytics init failed; disabling", exc_info=True)
            _client = None
        return _client


def is_enabled() -> bool:
    return _get_client() is not None


def capture(
    event: str,
    *,
    distinct_id: str,
    properties: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
) -> None:
    """Never raises. Without geoip, PostHog would locate every event at the server."""
    client = _get_client()
    if client is None:
        return
    try:
        client.capture(
            event,
            distinct_id=distinct_id,
            properties={"source": _SOURCE, **(properties or {})},
            groups=groups,
            disable_geoip=True,
        )
    except Exception:
        logger.debug("PostHog capture failed for %s", event, exc_info=True)


def shutdown() -> None:
    client = _client
    if client is None:
        return
    try:
        client.shutdown()
    except Exception:
        logger.debug("PostHog shutdown failed", exc_info=True)
