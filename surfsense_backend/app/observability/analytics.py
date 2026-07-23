"""Server-side PostHog product analytics for SurfSense.

Opt-in, mirroring the OpenTelemetry bootstrap contract: when
``POSTHOG_API_KEY`` is unset every function here is a silent no-op, so it is
safe to call from hot paths (including async request handlers) and from
self-hosted installs that never configure telemetry.

Design notes:
- The underlying ``posthog`` client enqueues events onto a background
  consumer thread, so ``capture()`` is a non-blocking queue append; the only
  network I/O happens off-thread. ``shutdown()`` flushes and joins that thread
  and MUST run before a process exits or queued events are lost.
- The client is created lazily on first use, never at import time. This keeps
  it fork-safe under Celery's prefork pool: a client (and its consumer thread)
  created in the parent would not survive ``fork()``, so each worker process
  builds its own on first capture.
- ``distinct_id`` is always ``str(user.id)`` so server events merge onto the
  same PostHog persons the web frontend identifies (see
  ``surfsense_web/components/providers/PostHogIdentify.tsx``).
- Every event passes ``disable_geoip=True``; without it PostHog would resolve
  the *server's* IP and overwrite each person's real (client-derived) location.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.config import config

if TYPE_CHECKING:
    from app.auth.context import AuthContext

logger = logging.getLogger(__name__)

_client: Any | None = None
_init_attempted = False
_lock = threading.Lock()

# Stamped on every backend event so client-observed (frontend) and
# server-truth events are always distinguishable in PostHog.
_SOURCE = "backend"


def _get_client() -> Any | None:
    """Return the process-local PostHog client, or ``None`` when disabled.

    Lazy + fork-safe: built on first use inside whichever process (web worker
    or Celery worker) calls it, never at import time.
    """
    global _client, _init_attempted

    if _init_attempted:
        return _client

    with _lock:
        if _init_attempted:
            return _client
        _init_attempted = True

        api_key = config.POSTHOG_API_KEY
        if not api_key:
            # ponytail: opt-in like OTel — no key means telemetry is off, not
            # a misconfiguration. Stay silent so self-hosters see no noise.
            return None

        try:
            from posthog import Posthog

            _client = Posthog(
                project_api_key=api_key,
                host=config.POSTHOG_HOST,
            )
        except Exception:
            logger.warning("PostHog analytics init failed; disabling", exc_info=True)
            _client = None

        return _client


def is_enabled() -> bool:
    """True when a PostHog client is configured and available."""
    return _get_client() is not None


def get_client() -> Any | None:
    """Raw PostHog client for integrations that need it (e.g. the LLM handler)."""
    return _get_client()


def _client_label(auth: AuthContext) -> str:
    """Best-effort ``client`` property derived from the auth principal.

    ``session`` can't be split into web vs desktop from auth alone, so callers
    that know better may override ``client`` in ``properties``.
    """
    if auth.method == "system":
        return auth.source or "system"
    if auth.method == "pat":
        return "pat"
    return "web"


def capture(
    event: str,
    *,
    distinct_id: str,
    properties: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
) -> None:
    """Capture a product event. No-op (and never raises) when disabled.

    Wrapped in try/except like the frontend ``safeCapture`` — analytics must
    never break a request. ``posthog`` v6 signature is ``capture(event,
    distinct_id=..., properties=...)`` (event first, distinct_id a kwarg).
    """
    client = _get_client()
    if client is None:
        return

    try:
        props = {"source": _SOURCE, **(properties or {})}
        client.capture(
            event,
            distinct_id=distinct_id,
            properties=props,
            groups=groups,
            disable_geoip=True,
        )
    except Exception:
        logger.debug("PostHog capture failed for %s", event, exc_info=True)


def capture_for(
    auth: AuthContext,
    event: str,
    properties: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
) -> None:
    """Capture an event attributed to an ``AuthContext`` principal.

    Derives ``distinct_id`` from the user id and stamps ``auth_method`` and a
    best-effort ``client`` so events are attributable to their surface
    (web/desktop/pat/gateway/automation).
    """
    if _get_client() is None:
        return

    props = {
        "auth_method": auth.method,
        "client": _client_label(auth),
        **(properties or {}),
    }
    capture(
        event,
        distinct_id=str(auth.user.id),
        properties=props,
        groups=groups,
    )


def group_identify(
    group_type: str,
    group_key: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Upsert group properties (e.g. per-workspace metadata). No-op when disabled."""
    client = _get_client()
    if client is None:
        return

    try:
        client.group_identify(
            group_type=group_type,
            group_key=group_key,
            properties=properties or {},
        )
    except Exception:
        logger.debug("PostHog group_identify failed for %s", group_type, exc_info=True)


def shutdown() -> None:
    """Flush queued events and stop the consumer thread. Safe to call always."""
    global _client
    client = _client
    if client is None:
        return
    try:
        client.shutdown()
    except Exception:
        logger.debug("PostHog shutdown failed", exc_info=True)


__all__ = [
    "capture",
    "capture_for",
    "get_client",
    "group_identify",
    "is_enabled",
    "shutdown",
]
