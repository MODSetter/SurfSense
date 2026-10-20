"""The OAuth routes: the browser's way back, the screen's poll and Cancel, and Sign in again."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from api.config import get_settings
from api.dependencies import SessionDep, transact
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_hosts import plugin_hosts, refused_hosts
from modules.plugins.installed.third_party_off import plugin_third_party_refusal
from modules.plugins.remote.sign_in.oauth.callback_page import (
    failed_page,
    signed_in_page,
)
from modules.plugins.remote.sign_in.oauth.oauth_credential import (
    OAUTH,
    read_credential,
)
from modules.plugins.remote.sign_in.oauth.own_app import OwnApp, own_app_auth
from modules.plugins.remote.sign_in.oauth.own_app_needed import OwnAppNeededError
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.sign_in_client import sign_in_client
from modules.plugins.remote.sign_in.oauth.sign_in_read import (
    SignInRead,
    SignInStarted,
    read_sign_in,
)
from modules.plugins.remote.sign_in.oauth.start_sign_in import (
    SignInsDep,
    start_sign_in,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get(
    "/oauth/callback",
    response_class=HTMLResponse,
    summary="Where the browser returns after signing in to a plugin",
)
async def oauth_callback(request: Request, sign_ins: SignInsDep) -> HTMLResponse:
    """Only a `state` this API issued is answered; any other changes nothing."""
    pending = sign_ins.deliver(dict(request.query_params))
    if pending is None:
        return failed_page(None, "It may have expired or been cancelled.")
    await sign_ins.finished(pending)
    if pending.status == "connected":
        return signed_in_page(pending.draft.name)
    return failed_page(
        pending.draft.name, pending.message or "The sign-in was not finished."
    )


@router.get(
    "/sign-ins/{sign_in_id}", response_model=SignInRead, summary="A sign-in's progress"
)
async def read_plugin_sign_in(sign_in_id: str, sign_ins: SignInsDep) -> SignInRead:
    pending = sign_ins.get(sign_in_id)
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such sign-in")
    return read_sign_in(pending)


@router.delete("/sign-ins/{sign_in_id}", status_code=204, summary="Abandon a sign-in")
async def cancel_plugin_sign_in(sign_in_id: str, sign_ins: SignInsDep) -> None:
    if not sign_ins.cancel(sign_in_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such sign-in")


class RedirectUri(BaseModel):
    redirect_uri: str


@router.get(
    "/oauth/redirect-uri",
    response_model=RedirectUri,
    summary="The callback a user registers their own OAuth app with",
)
def redirect_uri() -> RedirectUri:
    """The plugin host's page when packaged, the API's loopback one in a developer's build."""
    return RedirectUri(redirect_uri=sign_in_client(get_settings().port).redirect_uri)


class SignInAgainWrite(BaseModel):
    oauth_client: OwnApp | None = None


@router.post(
    "/{plugin_id}/sign-in",
    response_model=SignInStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sign in to a connected plugin again",
)
async def sign_in_again(
    plugin_id: str,
    request: Request,
    session: SessionDep,
    payload: SignInAgainWrite | None = None,
) -> SignInStarted:
    """The same row signs in again, so its tool settings stay.

    `oauth_client` switches it to the user's own app, or gives that app's secret again
    once disconnecting dropped it.
    """
    refusal = await transact(session, plugin_third_party_refusal, plugin_id)
    if refusal is not None:
        raise refusal

    def draft_of(s):
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None:
            return None
        app = payload.oauth_client if payload else None
        return _draft(plugin, app), plugin_hosts(plugin)

    found = await transact(session, draft_of)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    draft, hosts = found
    if draft is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_not_oauth",
                "message": "This plugin does not sign in with an account.",
            },
        )
    refusal = await transact(session, refused_hosts, hosts)
    if refusal is not None:
        raise refusal
    try:
        sign_in = await start_sign_in(session, request, draft)
    except OwnAppNeededError as needed:
        # Marked on the plugin; the screen answers with the user's own app.
        raise needed.refusal() from needed
    if sign_in is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_not_oauth",
                "message": "This plugin's server no longer asks to sign in with an account.",
            },
        )
    return sign_in


def _draft(plugin: InstalledPlugin, app: OwnApp | None = None) -> PluginDraft | None:
    auth = plugin.entry.get("auth", {})
    if plugin.credential_kind != OAUTH and auth.get("type") != OAUTH:
        return None
    credential = read_credential(plugin)
    entry = plugin.entry
    if app is not None:
        entry = {**entry, "auth": {**auth, **own_app_auth(app)}}
        auth = entry["auth"]
    client_id = auth.get("client_id")
    previous = credential.client if credential else None
    # The user's own app keeps its secret in the credential alone.
    secret = (
        app.client_secret
        if app is not None
        else previous.client_secret
        if previous is not None and previous.client_id == client_id
        else None
    )
    return PluginDraft(
        plugin_id=plugin.id,
        name=plugin.entry.get("name", plugin.id),
        url=plugin.url,
        source=plugin.source,
        entry=entry,
        scopes=_scopes(auth),
        client_id=client_id,
        client_secret=secret,
        previous_client=previous,
        existing=True,
    )


def _scopes(auth: dict) -> list[str] | None:
    """The scopes asked for before, and any a server's `insufficient_scope` named since."""
    scopes = list(
        dict.fromkeys([*auth.get("scopes", []), *auth.get("needs_scopes", [])])
    )
    return scopes or None
