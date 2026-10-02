"""The key opencode presents to the model endpoint, made fresh by each API process.

Loopback is open to every process on the machine, and this route spends the
user's remote API keys, so only the opencode SurfSense configured may call it.
"""

import hmac
import secrets

from fastapi import HTTPException, Request, status


def mint_launch_key() -> str:
    """A key no earlier run of the app knew."""
    return secrets.token_urlsafe(32)


def require_launch_key(request: Request) -> None:
    """Refuse a caller that does not hold this process's key."""
    expected = f"Bearer {request.app.state.agent_launch_key}".encode()
    presented = request.headers.get("authorization", "").encode()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "the agent's launch key is required"
        )
