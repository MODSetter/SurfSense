"""Posting events to PostHog's batch endpoint."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

DEFAULT_HOST = "https://us.i.posthog.com"
_BATCH_SIZE = 200
_TIMEOUT_SECONDS = 30


def send_batches(
    events: list[dict[str, Any]],
    *,
    api_key: str,
    host: str = DEFAULT_HOST,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> int:
    """Send every event and return how many were sent; raises on any refusal."""
    url = f"{(host or DEFAULT_HOST).rstrip('/')}/batch/"
    for start in range(0, len(events), _BATCH_SIZE):
        body = json.dumps(
            {"api_key": api_key, "batch": events[start : start + _BATCH_SIZE]}
        ).encode()
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        # urlopen raises HTTPError on a 4xx or 5xx, which fails the job.
        with opener(request, timeout=_TIMEOUT_SECONDS) as response:
            response.read()
    return len(events)
