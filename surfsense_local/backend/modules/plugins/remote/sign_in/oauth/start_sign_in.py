"""A sign-in from a connect route: discovery, consent for the authorization server's hosts,
then the authorization URL; or, for a server added by URL, the plugin saved to connect from
its row. The plugin's own hosts are allowed already."""

import logging
from dataclasses import replace
from typing import Annotated
from urllib.parse import urlsplit

import httpx2
from fastapi import Depends, HTTPException, Request, status
from mcp.client.auth import OAuthFlowError
from mcp.client.auth.exceptions import OAuthRegistrationError
from sqlalchemy.orm import Session

from api.config import get_settings
from api.dependencies import transact
from modules.plugins.installed.awaiting_sign_in import store_awaiting_sign_in
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.remote.sign_in.oauth.consented_client import HostNotAllowedError
from modules.plugins.remote.sign_in.oauth.handled_refusals import quiet_handled_refusals
from modules.plugins.remote.sign_in.oauth.oauth_discovery import discover_oauth
from modules.plugins.remote.sign_in.oauth.own_app_needed import (
    OwnAppNeededError,
    OwnAppReason,
    keep_needing_own_app,
)
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.plugin_sign_ins import (
    PluginSignIns,
    SignInEndedError,
)
from modules.plugins.remote.sign_in.oauth.registration_offer import (
    RegistrationOffer,
    registration_offer,
)
from modules.plugins.remote.sign_in.oauth.sign_in_client import sign_in_client
from modules.plugins.remote.sign_in.oauth.sign_in_read import SignInStarted, started

logger = logging.getLogger(__name__)
quiet_handled_refusals()


def get_sign_ins(request: Request) -> PluginSignIns:
    sign_ins = getattr(request.app.state, "plugin_sign_ins", None)
    if sign_ins is None:
        sign_ins = request.app.state.plugin_sign_ins = PluginSignIns()
    return sign_ins


SignInsDep = Annotated[PluginSignIns, Depends(get_sign_ins)]


async def save_for_sign_in(session: Session, draft: PluginDraft) -> bool:
    """Added by URL, saved signed out for Connect on its row: nothing is registered and no
    sign-in starts until then. False when the server's refusal does not ask for OAuth."""
    draft = await _discovered(session, draft)
    if draft is None:
        return False
    if await _registers_none(draft):
        await transact(session, keep_needing_own_app, draft, "needs_client")
    else:
        await transact(session, store_awaiting_sign_in, draft)
    return True


async def start_sign_in(
    session: Session, request: Request, draft: PluginDraft
) -> SignInStarted | None:
    """None when the server's refusal does not ask for OAuth."""
    draft = await _discovered(session, draft)
    if draft is None:
        return None
    if await _registers_none(draft):
        raise await _own_app_needed(session, draft, "needs_client")
    try:
        pending = await _started(request, draft)
    except OAuthRegistrationError as error:
        reason = await _registration_failure(draft)
        raise await _own_app_needed(session, draft, reason) from error
    except HostNotAllowedError as unasked:
        raise await _refusal(session, unasked) from unasked
    except (OAuthFlowError, httpx2.HTTPError, TimeoutError, SignInEndedError) as error:
        raise _sign_in_failed() from error
    if not pending.draft.existing:
        # Kept from here, signed out, so closing the browser loses nothing typed.
        await transact(session, store_awaiting_sign_in, pending.draft)
        pending.draft = replace(pending.draft, existing=True)
    return started(pending)


async def _discovered(session: Session, draft: PluginDraft) -> PluginDraft | None:
    """The draft with its authorization server's hosts, once the user allowed them."""
    try:
        discovery = await discover_oauth(draft.url, set(_draft_hosts(draft)))
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
    return draft.with_hosts(discovery.authorization_server_hosts)


async def _registers_none(draft: PluginDraft) -> bool:
    """Read before any registration, which would only be refused after requests sent for nothing."""
    offer = None if draft.client_id else await _offer(draft)
    if offer is None or _can_register(offer):
        return False
    logger.info("%s registers no apps; asking for the user's own", _host(draft))
    return True


async def _started(request: Request, draft: PluginDraft):
    """A public client first; refused, a client with a secret of this install's own."""
    start = get_sign_ins(request).start
    hosts = set(_draft_hosts(draft))
    factory, port = request.app.state.session_factory, get_settings().port
    try:
        return await start(draft, hosts, factory, port)
    except OAuthRegistrationError:
        if draft.client_id or draft.confidential:
            raise
        logger.info(
            "%s refused SurfSense as a public client; registering with a secret",
            _host(draft),
        )
        return await start(replace(draft, confidential=True), hosts, factory, port)


async def _offer(draft: PluginDraft) -> RegistrationOffer | None:
    """None when it cannot be read: the sign-in then tries, as the spec has a client do."""
    try:
        return await registration_offer(draft.url, set(_draft_hosts(draft)))
    except (HostNotAllowedError, httpx2.HTTPError):
        return None


def _can_register(offer: RegistrationOffer) -> bool:
    """Dynamic registration, or a client document where this build signs in with one."""
    documents = sign_in_client(get_settings().port).client_metadata_url is not None
    return offer.registers or (offer.client_documents and documents)


async def _registration_failure(draft: PluginDraft) -> OwnAppReason:
    """No registration at all is the user's own app; registration that refused us is said so."""
    offer = await _offer(draft)
    if offer and offer.registers:
        logger.info("%s refused to register SurfSense", _host(draft))
        return "refused"
    logger.info("%s registers no apps; asking for the user's own", _host(draft))
    return "needs_client"


async def _own_app_needed(
    session: Session, draft: PluginDraft, reason: OwnAppReason
) -> OwnAppNeededError:
    """Kept, a new plugin stored and a saved one marked, before the caller is told."""
    await transact(session, keep_needing_own_app, draft, reason)
    return OwnAppNeededError(reason)


def _host(draft: PluginDraft) -> str:
    return urlsplit(draft.url).hostname or draft.url


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
