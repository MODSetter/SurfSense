"""Starting a sign-in from a connect route: discovery, consent for the authorization
server's hosts, then the authorization URL. The plugin's own hosts are allowed already."""

from typing import Annotated
from urllib.parse import urlsplit

import httpx2
from fastapi import Depends, HTTPException, Request, status
from mcp.client.auth import OAuthFlowError
from sqlalchemy.orm import Session

from api.config import get_settings
from api.dependencies import transact
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.remote.sign_in.oauth.consented_client import HostNotAllowedError
from modules.plugins.remote.sign_in.oauth.oauth_discovery import discover_oauth
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.plugin_sign_ins import (
    PluginSignIns,
    SignInEndedError,
)
from modules.plugins.remote.sign_in.oauth.sign_in_read import SignInStarted, started


def get_sign_ins(request: Request) -> PluginSignIns:
    sign_ins = getattr(request.app.state, "plugin_sign_ins", None)
    if sign_ins is None:
        sign_ins = request.app.state.plugin_sign_ins = PluginSignIns()
    return sign_ins


SignInsDep = Annotated[PluginSignIns, Depends(get_sign_ins)]


async def start_sign_in(
    session: Session, request: Request, draft: PluginDraft
) -> SignInStarted | None:
    """None when the server's refusal does not ask for OAuth."""
    allowed = set(_draft_hosts(draft))
    try:
        discovery = await discover_oauth(draft.url, allowed)
    except HostNotAllowedError as unasked:
        raise await _refusal(session, unasked) from unasked
    except httpx2.HTTPError as error:
        raise _sign_in_failed() from error
    if discovery is None:
        return None
    refusal = await transact(
        session, refused_hosts, discovery.authorization_server_hosts
    )
    if refusal is not None:
        raise refusal

    draft = draft.with_hosts(discovery.authorization_server_hosts)
    try:
        pending = await get_sign_ins(request).start(
            draft,
            set(_draft_hosts(draft)),
            request.app.state.session_factory,
            get_settings().port,
        )
    except HostNotAllowedError as unasked:
        raise await _refusal(session, unasked) from unasked
    except (OAuthFlowError, httpx2.HTTPError, TimeoutError, SignInEndedError) as error:
        raise _sign_in_failed() from error
    return started(pending)


def _draft_hosts(draft: PluginDraft) -> list[str]:
    hosts = [urlsplit(draft.url).hostname or "", *draft.entry.get("hosts", [])]
    return list(dict.fromkeys(host for host in hosts if host))


async def _refusal(session: Session, unasked: HostNotAllowedError) -> Exception:
    """The prompt's question for a host discovery named; a host allowed since gets a retry."""
    refusal = await transact(session, refused_hosts, [unasked.host])
    return refusal or _sign_in_failed()


def _sign_in_failed() -> HTTPException:
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        {
            "code": "plugin_sign_in_failed",
            "message": "The plugin's sign-in could not be started.",
        },
    )
