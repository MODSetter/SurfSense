import httpx

from modules.llm.subscriptions.chatgpt.endpoints import RESOURCE, get_endpoints

# Under the database's 5 s busy_timeout: a refresh holds the write lock, and a
# writer kept waiting longer than that fails instead of waiting.
REFRESH_TIMEOUT = httpx.Timeout(4.0, connect=2.0)
EXCHANGE_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
# OpenAI's codes for a token set that cannot come back; anything else is transient.
DEAD = {"invalid_grant", "token_expired", "refresh_token_invalidated"}


class TokenRefusedError(Exception):
    """OpenAI will not issue tokens from this grant again; sign in anew."""


def refresh(client_id: str, refresh_token: str) -> dict:
    """A new token set for a refresh token. Synchronous: it runs under the write lock."""
    reply = httpx.post(
        get_endpoints().token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
            "resource": RESOURCE,
        },
        timeout=REFRESH_TIMEOUT,
    )
    return _tokens(reply)


async def exchange_code(
    client_id: str, code: str, verifier: str, redirect_uri: str
) -> dict:
    async with httpx.AsyncClient(timeout=EXCHANGE_TIMEOUT) as client:
        reply = await client.post(
            get_endpoints().token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
                "resource": RESOURCE,
            },
        )
    return _tokens(reply)


def _tokens(reply: httpx.Response) -> dict:
    if reply.status_code in (400, 401):
        try:
            error = reply.json().get("error")
        except ValueError:
            error = None
        if error in DEAD:
            raise TokenRefusedError(error)
    reply.raise_for_status()
    payload = reply.json()
    if not isinstance(payload, dict) or not isinstance(
        payload.get("access_token"), str
    ):
        raise ValueError("the token endpoint returned no access token")
    return payload
