"""The OAuth `state` SurfSense sends: `<port>.<nonce>`, so the plugin host's callback page
can forward the browser to the API's loopback port. The port is the API's own; the nonce
is the SDK's own state, which it checks again on the way back."""

import re

_STATE = re.compile(r"^(?P<port>[0-9]{4,5})\.(?P<nonce>[A-Za-z0-9_-]{16,256})$")


def state_for(port: int, nonce: str) -> str:
    if not 1024 <= port <= 65535 or not _STATE.match(f"{port}.{nonce}"):
        raise ValueError("the sign-in state must carry a loopback port and a nonce")
    return f"{port}.{nonce}"


def nonce_of(state: str) -> str | None:
    """None for a state SurfSense never shapes, so it is refused before any lookup."""
    matched = _STATE.match(state)
    return matched["nonce"] if matched else None
