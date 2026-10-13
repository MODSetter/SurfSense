"""Refreshing an OAuth plugin's access token with its refresh token.

One refresh per plugin at a time: providers rotate refresh tokens, so two at once would
spend the same one twice and the second would sign the user out. A refusal (a revoked or
expired grant) marks the plugin to sign in again; a provider that cannot be reached
leaves the sign-in as it was, to try at the next turn.
"""

import asyncio
import base64
import enum
from datetime import UTC, datetime
from urllib.parse import quote

import httpx2
from mcp.shared.auth import OAuthToken
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress.service import EgressDeniedError, host_destination, require
from modules.plugins.installed.models import CheckFailure, InstalledPlugin
from modules.plugins.remote.sign_in.oauth.oauth_credential import (
    OAuthCredential,
    read_credential,
    write_credential,
)

REFRESH_TIMEOUT_SECONDS = 30

# By event loop too: a lock is bound to the loop it first waited on.
_locks: dict[tuple[int, str], asyncio.Lock] = {}


class Refresh(enum.Enum):
    UNCHANGED = "unchanged"
    REFRESHED = "refreshed"
    SIGNED_OUT = "signed_out"


class _RefusedError(Exception):
    pass


async def refresh_sign_in(
    session: Session,
    plugin_id: str,
    *,
    within_seconds: float | None = None,
    refused_token: str | None = None,
) -> Refresh:
    """Refreshes when the token expires within `within_seconds`, or is the one a server refused.

    A token another caller refreshed meanwhile counts as refreshed, without a request.
    """
    key = (id(asyncio.get_running_loop()), plugin_id)
    async with _locks.setdefault(key, asyncio.Lock()):
        credential = await transact(session, _reachable_credential, plugin_id)
        if credential is None:
            return Refresh.UNCHANGED
        if (
            refused_token is not None
            and credential.tokens.access_token != refused_token
        ):
            return Refresh.REFRESHED
        if within_seconds is not None and not credential.expires_within(within_seconds):
            return Refresh.UNCHANGED
        try:
            tokens = await _refreshed_tokens(credential)
        except _RefusedError:
            await transact(session, _signed_out, plugin_id)
            return Refresh.SIGNED_OUT
        except (httpx2.HTTPError, ValidationError):
            return Refresh.UNCHANGED
        await transact(session, _store, plugin_id, credential.refreshed(tokens))
        return Refresh.REFRESHED


def _reachable_credential(session: Session, plugin_id: str) -> OAuthCredential | None:
    """None for a plugin not signed in with OAuth, or whose token endpoint's host is off."""
    plugin = session.get(InstalledPlugin, plugin_id)
    credential = None if plugin is None else read_credential(plugin)
    if credential is None:
        return None
    try:
        require(session, host_destination(credential.token_endpoint))
    except EgressDeniedError:
        return None
    return credential


async def _refreshed_tokens(credential: OAuthCredential) -> OAuthToken:
    if not credential.tokens.refresh_token:
        raise _RefusedError
    client = credential.client
    form = {
        "grant_type": "refresh_token",
        "refresh_token": credential.tokens.refresh_token,
        "client_id": client.client_id,
    }
    if credential.resource:
        form["resource"] = credential.resource
    headers: dict[str, str] = {}
    # SurfSense registers as a public client; a server may still have assigned a secret.
    if (
        client.client_secret
        and client.token_endpoint_auth_method == "client_secret_basic"
    ):
        pair = (
            f"{quote(client.client_id, safe='')}:{quote(client.client_secret, safe='')}"
        )
        headers["authorization"] = f"Basic {base64.b64encode(pair.encode()).decode()}"
    elif (
        client.client_secret
        and client.token_endpoint_auth_method == "client_secret_post"
    ):
        form["client_secret"] = client.client_secret
    async with httpx2.AsyncClient(timeout=REFRESH_TIMEOUT_SECONDS) as http:
        answer = await http.post(credential.token_endpoint, data=form, headers=headers)
    if answer.status_code in (400, 401):
        raise _RefusedError
    answer.raise_for_status()
    return OAuthToken.model_validate_json(answer.content)


def _store(session: Session, plugin_id: str, credential: OAuthCredential) -> None:
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is not None:
        write_credential(plugin, credential)


def _signed_out(session: Session, plugin_id: str) -> None:
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is not None:
        plugin.check_failure = CheckFailure.SIGN_IN
        plugin.checked_at = datetime.now(UTC)
