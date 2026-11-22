"""The one HTTP client every live request goes through, with its limits."""

import httpx2

# A listed server answers a listing in well under this; a slower one would stall a turn.
TIMEOUT_SECONDS = 15.0
USER_AGENT = "SurfSense-registry-check"


def web_client(*, on_response=None) -> httpx2.AsyncClient:
    hooks = {"response": [on_response]} if on_response else {}
    return httpx2.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        headers={"user-agent": USER_AGENT},
        event_hooks=hooks,
    )
