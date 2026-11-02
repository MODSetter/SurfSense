"""Sign-ins under way, held in the API's memory: a restart ends them, and Connect starts again.

Each runs as a task: the SDK's flow waits on the browser, the callback route hands it the
code, and only then are the tools listed and the plugin stored.
"""

import asyncio
import contextlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx2
from mcp.client.auth import OAuthFlowError
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientInformationFull
from sqlalchemy.orm import Session

from api.config import get_settings
from modules.plugins.installed.models import PluginSource
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.oauth.browser_origin import BrowserOrigin
from modules.plugins.remote.sign_in.oauth.consented_client import HostNotAllowedError
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAuthCredential
from modules.plugins.remote.sign_in.oauth.pending_storage import PendingStorage
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.sign_in_client import (
    SignInClient,
    sign_in_client,
)
from modules.plugins.remote.sign_in.oauth.sign_in_failure import SignInFailure
from modules.plugins.remote.sign_in.oauth.sign_in_flow import sign_in
from modules.plugins.remote.sign_in.oauth.sign_in_state import nonce_of, state_for
from modules.plugins.remote.sign_in.oauth.signed_in_plugin import (
    NotStoredError,
    store_signed_in,
)
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.streamable_only import listed_streamable

# Long enough to sign in and approve in a browser; an abandoned one is then forgotten.
SIGN_IN_SECONDS = 600
# Discovery and registration, before the browser opens.
START_SECONDS = 60
# What the callback page waits for: the token exchange and the listing.
FINISH_SECONDS = 60
# A settled sign-in stays readable this long past its expiry, for the screen's last poll.
FORGET_AFTER_SECONDS = 60

SignInStatus = Literal["waiting", "connected", "failed"]
SessionFactory = Callable[[], Session]

logger = logging.getLogger(__name__)


class SignInEndedError(Exception):
    """The provider refused, the user took too long, or the sign-in was cancelled."""

    def __init__(self, code: SignInFailure, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class PendingSignIn:
    id: str
    draft: PluginDraft
    expires_at: float
    status: SignInStatus = "waiting"
    # Why it failed, once it has: the code, its sentence, and the host or the
    # name the sentence names, as raw values for the screen's own sentence.
    failure: SignInFailure | None = None
    message: str | None = None
    failure_host: str | None = None
    failure_name: str | None = None
    authorization_url: str = ""
    nonce: str | None = None
    started: asyncio.Future[None] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )
    code: asyncio.Future[AuthorizationCodeResult] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )
    task: asyncio.Task | None = field(default=None, repr=False)


class PluginSignIns:
    def __init__(self) -> None:
        self._pending: dict[str, PendingSignIn] = {}

    def get(self, sign_in_id: str) -> PendingSignIn | None:
        self._forget_expired()
        return self._pending.get(sign_in_id)

    def cancel(self, sign_in_id: str) -> bool:
        pending = self._pending.pop(sign_in_id, None)
        if pending is None:
            return False
        if not pending.started.done():
            pending.started.set_exception(
                SignInEndedError(
                    SignInFailure.NOT_FINISHED, "The sign-in was cancelled."
                )
            )
        if pending.task is not None:
            pending.task.cancel()
        return True

    def cancel_third_party(self) -> None:
        """Third-party plugins turned off: no sign-in under way reaches its provider after."""
        for sign_in_id, pending in list(self._pending.items()):
            if pending.draft.source != PluginSource.FIRST_PARTY:
                self.cancel(sign_in_id)

    async def start(
        self,
        draft: PluginDraft,
        allowed_hosts: set[str],
        session_factory: SessionFactory,
        origin: BrowserOrigin,
    ) -> PendingSignIn:
        """Answers once the authorization URL is ready; raises what stopped it before."""
        self._forget_expired()
        for earlier in [
            p for p in self._pending.values() if p.draft.plugin_id == draft.plugin_id
        ]:
            self.cancel(earlier.id)
        loop = asyncio.get_running_loop()
        pending = PendingSignIn(
            secrets.token_urlsafe(16), draft, loop.time() + SIGN_IN_SECONDS
        )
        self._pending[pending.id] = pending
        pending.task = asyncio.create_task(
            self._run(pending, allowed_hosts, session_factory, origin)
        )
        try:
            await asyncio.wait_for(asyncio.shield(pending.started), START_SECONDS)
        except BaseException:
            self.cancel(pending.id)
            raise
        return pending

    def deliver(self, query: dict[str, str]) -> PendingSignIn | None:
        """Hands the browser's answer to its sign-in; None for a state SurfSense did not issue."""
        nonce = nonce_of(query.get("state", ""))
        pending = next(
            (
                p
                for p in self._pending.values()
                if nonce is not None
                and p.nonce is not None
                and secrets.compare_digest(p.nonce, nonce)
            ),
            None,
        )
        if pending is None or pending.code.done():
            return None
        if "error" in query:
            pending.code.set_exception(
                SignInEndedError(*_provider_refusal(query["error"]))
            )
        elif not query.get("code"):
            pending.code.set_exception(
                SignInEndedError(
                    SignInFailure.NOT_FINISHED, "The sign-in carried no code."
                )
            )
        else:
            pending.code.set_result(
                AuthorizationCodeResult(
                    code=query["code"], state=nonce, iss=query.get("iss")
                )
            )
        return pending

    async def finished(self, pending: PendingSignIn) -> None:
        if pending.task is None:
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(pending.task), FINISH_SECONDS)

    def _forget_expired(self) -> None:
        forget_before = asyncio.get_running_loop().time() - FORGET_AFTER_SECONDS
        for sign_in_id in [
            k for k, p in self._pending.items() if p.expires_at < forget_before
        ]:
            self.cancel(sign_in_id)

    async def _run(
        self,
        pending: PendingSignIn,
        allowed_hosts: set[str],
        session_factory: SessionFactory,
        origin: BrowserOrigin,
    ) -> None:
        client = sign_in_client(origin)
        draft = pending.draft

        async def open_browser(url: str) -> None:
            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query))
            pending.nonce = query["state"]
            # The port is read only by the plugin host's page, which forwards a
            # loopback sign-in; another origin's callback is the API itself.
            port = origin.port if origin.is_loopback else get_settings().port
            query["state"] = state_for(port, pending.nonce)
            if draft.scopes:
                query["scope"] = " ".join(draft.scopes)
            pending.authorization_url = parts._replace(query=urlencode(query)).geturl()
            pending.started.set_result(None)

        async def code_returned() -> AuthorizationCodeResult:
            remaining = pending.expires_at - asyncio.get_running_loop().time()
            try:
                return await asyncio.wait_for(pending.code, max(remaining, 0))
            except TimeoutError:
                raise SignInEndedError(
                    SignInFailure.TIMED_OUT, "The sign-in was not finished in time."
                ) from None

        try:
            credential = await sign_in(
                draft.url,
                client,
                PendingStorage(_known_client(draft, client)),
                draft.scopes,
                allowed_hosts,
                open_browser,
                code_returned,
                draft.confidential,
            )
            # As adding a server without a sign-in does: Streamable HTTP alone, an
            # address that answers only the older SSE refused as one.
            tools = await listed_streamable(
                draft.url, token_headers(credential.tokens.access_token)
            )
            # The draft as it is now: saved before the browser came back, it signs in again.
            stored = pending.draft
            await asyncio.to_thread(_store, session_factory, stored, credential, tools)
            pending.status = "connected"
        except Exception as error:
            if not pending.started.done():
                pending.started.set_exception(error)
                return
            pending.status = "failed"
            pending.failure, pending.message = _failure(error)
            if isinstance(error, HostNotAllowedError):
                pending.failure_host = error.host
            elif isinstance(error, NotStoredError):
                pending.failure_name = error.name
            # The type alone: an SDK message can quote a provider's response.
            logger.warning(
                "signing in to %s failed: %s", draft.plugin_id, type(error).__name__
            )


def _known_client(
    draft: PluginDraft, client: SignInClient
) -> OAuthClientInformationFull | None:
    """A pre-registered client wins; an earlier registration is reused only for the same redirect."""
    if draft.client_id:
        return OAuthClientInformationFull(
            client_id=draft.client_id,
            client_secret=draft.client_secret,
            token_endpoint_auth_method=(
                "client_secret_post" if draft.client_secret else "none"
            ),
            redirect_uris=[client.redirect_uri],
        )
    previous = draft.previous_client
    if previous and client.redirect_uri in {
        str(u) for u in previous.redirect_uris or []
    }:
        return previous
    return None


def _store(
    session_factory: SessionFactory,
    draft: PluginDraft,
    credential: OAuthCredential,
    tools: list,
) -> None:
    with session_factory() as session:
        store_signed_in(session, draft, credential, tools)
        session.commit()


def _provider_refusal(error: str) -> tuple[SignInFailure, str]:
    if error == "access_denied":
        return SignInFailure.DECLINED, "The sign-in was declined."
    return SignInFailure.REFUSED, f"The sign-in was refused ({error})."


def _failure(error: Exception) -> tuple[SignInFailure, str]:
    if isinstance(error, (SignInEndedError, NotStoredError)):
        return error.code, str(error)
    if isinstance(error, HostNotAllowedError):
        return (
            SignInFailure.HOST_NOT_ALLOWED,
            f"SurfSense isn't allowed to contact {error.host}.",
        )
    if isinstance(error, ServerError):
        return (
            SignInFailure.TOOLS_NOT_LISTED,
            f"Signed in, but the server could not list its tools: {error}.",
        )
    if isinstance(error, httpx2.HTTPError):
        return (
            SignInFailure.SERVER_UNREACHABLE,
            "The sign-in server could not be reached.",
        )
    if isinstance(error, OAuthFlowError):
        return SignInFailure.NOT_FINISHED, "The sign-in could not be finished."
    return SignInFailure.FAILED, "The sign-in failed."
