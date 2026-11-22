"""The key a runtime presents to reach one thread's plugins through the gateway.

Derived from the API process's launch key, so it opens nothing else and dies with the
process. Per thread, not per turn: a new key would make the runtime connect again and
lose its MCP session with each plugin.
"""

import hashlib
import hmac

from fastapi import HTTPException, Request, status


def gateway_key(launch_key: str, workspace_id: int, thread_id: int) -> str:
    message = f"plugin-gateway:{workspace_id}:{thread_id}".encode()
    return hmac.new(launch_key.encode(), message, hashlib.sha256).hexdigest()


def require_gateway_key(request: Request, workspace_id: int, thread_id: int) -> None:
    key = gateway_key(request.app.state.agent_launch_key, workspace_id, thread_id)
    presented = request.headers.get("authorization", "").encode()
    if not hmac.compare_digest(presented, f"Bearer {key}".encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "this thread's plugin key is required"
        )
