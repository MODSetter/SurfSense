"""The one client every verb reaches the app through, over loopback.

Not through http: loopback is not egress, so no host check and no log line.
"""

import json
import urllib.error
import urllib.request
from typing import cast

from surfsense_plugin_sdk.app.context import api_url, workspace_id

# A route that takes this long is stuck, not busy.
TIMEOUT_SECONDS = 60

# No proxy: a proxy cannot reach this computer's 127.0.0.1, where the app listens.
_opener_without_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class AppRefused(Exception):
    """The app answered with an error; the message is the app's own."""


def get_from_workspace(path: str) -> object:
    """Reads through a route in the run's workspace."""
    return _send("GET", path, None)


def post_to_workspace(path: str, body: object) -> object:
    """Creates something through a route in the run's workspace."""
    return _send("POST", path, body)


def patch_in_workspace(path: str, body: object) -> object:
    """Changes something through a route in the run's workspace."""
    return _send("PATCH", path, body)


def _send(method: str, path: str, body: object) -> object:
    """Shared by every call: the app's address, no proxy, a timeout, its reasons."""
    # The URL first: with neither set, the app is what is missing.
    url = api_url()
    payload = None if body is None else json.dumps(body).encode()
    # A body with no Content-Type is labelled a form by urllib, and the app then
    # refuses it: FastAPI reads JSON only when told it is JSON.
    headers = {} if payload is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(
        f"{url}/workspaces/{workspace_id()}{path}",
        method=method,
        data=payload,
        headers=headers,
    )
    try:
        with _opener_without_proxy.open(request, timeout=TIMEOUT_SECONDS) as response:
            reply: object = json.loads(response.read() or b"null")
            return reply
    except urllib.error.HTTPError as refusal:
        raise AppRefused(_reason(refusal)) from None


def _reason(refusal: urllib.error.HTTPError) -> str:
    """The app's own explanation of a refusal, whichever shape FastAPI gave it."""
    try:
        detail: object = cast(dict[str, object], json.loads(refusal.read()))["detail"]
    except (ValueError, TypeError, KeyError):
        detail = None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        message = cast(dict[str, object], detail).get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, list):
        return "; ".join(_field_error(error) for error in cast(list[object], detail))
    return f"SurfSense refused the request: {refusal.reason}"


def _field_error(error: object) -> str:
    """One of FastAPI's validation errors, as the field and what is wrong with it."""
    if not isinstance(error, dict):
        return str(error)
    fields = cast(dict[str, object], error)
    location = fields.get("loc")
    parts = cast(list[object], location) if isinstance(location, list) else []
    where = ".".join(str(part) for part in parts if part != "body")
    message = str(fields.get("msg", "is not valid"))
    return f"{where}: {message}" if where else message
