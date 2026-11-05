"""Which chat error kind an error opencode reports is, so the screen offers the same fix."""

import json
from typing import Any

from modules.llm.connections.console_refusals import PROVIDER_REFUSED

# What SurfSense's model endpoint codes in its error body.
RELAY_KINDS = frozenset(
    {"subscription_limit", "subscription_sign_in", PROVIDER_REFUSED}
)


def error_kind(error: dict[str, Any]) -> str:
    """A refusal SurfSense's relay coded keeps its chat kind; anything else is `unknown`."""
    body = (error.get("response") or {}).get("body")
    try:
        code = json.loads(body)["error"]["code"] if isinstance(body, str) else None
    except (ValueError, KeyError, TypeError):
        code = None
    return code if code in RELAY_KINDS else "unknown"
