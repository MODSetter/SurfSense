"""The `/plugins/registry` routes: third-party plugins from the signed registry."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from api.dependencies import SessionDep, transact
from modules.plugins.installed.custom_plugin import connected_name
from modules.plugins.installed.models import InstalledPlugin, PluginSource
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.installed.plugin_read import PluginRead, read_plugin
from modules.plugins.installed.registry_plugin import store_registry_plugin
from modules.plugins.installed.third_party import third_party_on
from modules.plugins.installed.third_party_off import third_party_refusal
from modules.plugins.lists.icon_response import icon_response
from modules.plugins.lists.registry import registry_origin
from modules.plugins.lists.registry.current_registry import (
    CurrentRegistry,
    local_registry,
    refreshed_registry,
)
from modules.plugins.lists.registry.entry_headers import filled_headers
from modules.plugins.lists.registry.registry_consent import registry_refusal
from modules.plugins.lists.registry.registry_entry import RegistryEntry
from modules.plugins.lists.registry.registry_icons import icon_file
from modules.plugins.lists.registry.registry_read import RegistryRead, read_registry
from modules.plugins.remote.connect_refusal import connect_refusal
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.headers.given_headers import as_sent
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.oauth.own_app import (
    OwnApp,
    own_app_auth,
)
from modules.plugins.remote.sign_in.oauth.own_app_needed import (
    OwnAppNeededError,
    keep_needing_own_app,
)
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.sign_in_read import SignInStarted
from modules.plugins.remote.sign_in.oauth.start_sign_in import start_sign_in
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.source import RemoteMcpSource

router = APIRouter(prefix="/plugins/registry", tags=["plugins"])


class RegistryConnect(BaseModel):
    # The key a `token` entry asks for; nothing for `none`.
    token: str | None = None
    # A value for each header a `headers` entry names.
    headers: list[SignInHeader] | None = None
    # The user's own app, for an `oauth` entry marked `user_client`.
    oauth_client: OwnApp | None = None


@router.get("", response_model=RegistryRead, summary="List third-party plugins")
async def list_registry(session: SessionDep) -> RegistryRead:
    """Refreshed at most every few minutes; never fetched while third-party plugins are off."""
    if not await transact(session, third_party_on):
        return RegistryRead(third_party_off=True)
    current = await _registry(session)
    return await transact(session, read_registry, current)


@router.post(
    "/{plugin_id}",
    response_model=PluginRead | SignInStarted,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a third-party plugin from the registry",
)
async def connect_registry_plugin(
    plugin_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    payload: RegistryConnect | None = None,
) -> PluginRead | SignInStarted:
    """From the copy the screen listed, refreshed as listing would.

    An `oauth` entry answers `202` with the sign-in's page; it is stored once signed in.
    """
    token = payload.token if payload else None
    refusal = await transact(session, third_party_refusal, PluginSource.REGISTRY)
    if refusal is not None:
        raise refusal
    entry = (await _registry(session)).document.entry(plugin_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not listed")

    def connected_as(s):
        if s.get(InstalledPlugin, plugin_id) is not None:
            return entry.name
        return connected_name(s, entry.url)

    taken = await transact(session, connected_as)
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "plugin_already_connected",
                "message": f"This server is already connected as {taken}.",
                "name": taken,
            },
        )
    refusal = await transact(session, refused_hosts, entry.hosts)
    if refusal is not None:
        raise refusal

    if entry.auth.type == "oauth":
        app = payload.oauth_client if payload else None
        if entry.auth.user_client and app is None:
            # Kept before any request, set up from its row like any other needing one.
            await transact(session, keep_needing_own_app, _draft(entry), "needs_client")
            return await transact(
                session,
                lambda s: read_plugin(s, s.get_one(InstalledPlugin, plugin_id)),
            )
        try:
            sign_in = await start_sign_in(session, request, _draft(entry, app))
        except OwnAppNeededError:
            # Kept, needing the user's own app, and set up from its row.
            return await transact(
                session,
                lambda s: read_plugin(s, s.get_one(InstalledPlugin, plugin_id)),
            )
        if sign_in is None:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                {
                    "code": "plugin_sign_in_failed",
                    "message": "The plugin's server did not ask to sign in.",
                },
            )
        response.status_code = status.HTTP_202_ACCEPTED
        return sign_in

    key = token if entry.auth.type == "token" else None
    headers = (
        filled_headers(entry.auth.headers or [], payload.headers if payload else None)
        if entry.auth.type == "headers"
        else None
    )
    sent = as_sent(headers) if headers else token_headers(key)
    source = RemoteMcpSource(entry.url, sent)
    try:
        tools = await source.list_tools()
    except ServerError as error:
        raise connect_refusal(error) from error
    finally:
        await source.close()

    def store(s):
        stored = store_registry_plugin(s, entry, key, tools, headers)
        return read_plugin(s, stored)

    return await transact(session, store)


def _draft(entry: RegistryEntry, app: OwnApp | None = None) -> PluginDraft:
    listed = entry.model_dump(exclude_none=True)
    if app is not None:
        listed = {**listed, "auth": {**listed["auth"], **own_app_auth(app)}}
    return PluginDraft(
        plugin_id=entry.id,
        name=entry.name,
        url=entry.url,
        source=PluginSource.REGISTRY,
        entry=listed,
        scopes=(app.scopes if app and app.scopes else None) or entry.auth.scopes,
        client_id=app.client_id.strip() if app else entry.auth.client_id,
        client_secret=app.client_secret if app else None,
    )


# An SVG opened on its own runs nothing and loads nothing from the API's origin.
@router.get("/icons/{plugin_id}", summary="A third-party plugin's icon")
def registry_icon(plugin_id: str, session: SessionDep) -> Response:
    """From the copy already held: never fetched here."""
    current = local_registry() if third_party_on(session) else None
    entry = current.document.entry(plugin_id) if current else None
    path = icon_file(entry) if entry else None
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} has no icon")
    return icon_response(path)


async def _registry(session: SessionDep) -> CurrentRegistry:
    if not registry_origin.reads_repository():
        refusal = await transact(session, registry_refusal)
        if refusal is not None:
            raise refusal
    current = await refreshed_registry()
    if current is None:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            {
                "code": "registry_unavailable",
                "message": "The list of third-party plugins could not be fetched.",
            },
        )
    return current
