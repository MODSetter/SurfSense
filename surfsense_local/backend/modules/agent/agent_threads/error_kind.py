"""Which chat error kind an error opencode reports is, so the screen offers the same fix."""

import json
from typing import Any

# What SurfSense's model endpoint names a plan's refusal in its error body.
PLAN_KINDS = frozenset({"subscription_limit", "subscription_sign_in"})


def error_kind(error: dict[str, Any]) -> str:
    """A plan refusal SurfSense's relay coded keeps its chat kind; anything else is `unknown`."""
    body = (error.get("data") or {}).get("responseBody")
    try:
        code = json.loads(body)["error"]["code"] if isinstance(body, str) else None
    except (ValueError, KeyError, TypeError):
        code = None
    return code if code in PLAN_KINDS else "unknown"
