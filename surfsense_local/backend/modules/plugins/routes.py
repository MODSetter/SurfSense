"""The `/plugins` routes: connecting, listing and switching plugins, the same for every kind."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from api.dependencies import SessionDep, transact
from modules.plugins.installed.custom_plugin import (
    connected_name,
    custom_plugin_id,
    store_custom_plugin,
    url_host,
)
from modules.plugins.installed.disconnect import disconnect
from modules.plugins.installed.first_party_plugin import store_first_party_plugin
from modules.plugins.installed.https_required import needs_https
from modules.plugins.installed.models import (
    CheckFailure,
    InstalledPlugin,
    PluginSource,
    ToolApproval,
)
from modules.plugins.installed.plugin_check import check_failure, record_check
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.installed.plugin_key import replace_key
from modules.plugins.installed.plugin_read import PluginRead, read_plugin, read_plugins
from modules.plugins.installed.plugin_switch import set_plugin_enabled
from modules.plugins.installed.remove import remove
from modules.plugins.installed.server_url import server_url
from modules.plugins.installed.third_party import set_third_party_on, third_party_on
from modules.plugins.installed.tool_settings import set_tool
from modules.plugins.lists.first_party.entry_read import (
    FirstPartyEntryRead,
    read_first_party,
)
from modules.plugins.lists.first_party.first_party_icon import first_party_icon
from modules.plugins.lists.first_party.first_party_list import first_party_entries
from modules.plugins.lists.icon_response import icon_response
from modules.plugins.remote.connect_refusal import connect_refusal
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.oauth.listed_after_refresh import (
    list_once,
    listed_after_refresh,
)
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.sign_in_read import SignInStarted
from modules.plugins.remote.sign_in.oauth.start_sign_in import start_sign_in
from modules.plugins.remote.sign_in.plugin_headers import (
    LICENSE,
    license_headers,
    sign_in_headers,
)
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.source import RemoteMcpSource

router = APIRouter(prefix="/plugins", tags=["plugins"])


class ToolWrite(BaseModel):
    enabled: bool | None = None
    approval: ToolApproval | None = None


class PluginWrite(BaseModel):
    enabled: bool


class ThirdPartyAllowed(BaseModel):
    allowed: bool


class KeyWrite(BaseModel):
    token: str


class CustomPluginWrite(BaseModel):
    url: str
    name: str
    token: str | None = None


@router.get("", response_model=list[PluginRead], summary="List connected plugins")
def list_plugins(session: SessionDep) -> list[PluginRead]:
    return read_plugins(session)


@router.post(
    "/custom",
    response_model=PluginRead | SignInStarted,
    status_code=status.HTTP_201_CREATED,
    summary="Add a remote server by URL",
)
async def add_custom_plugin(
    payload: CustomPluginWrite,
    request: Request,
    response: Response,
    session: SessionDep,
) -> PluginRead | SignInStarted:
    """A server whose refusal asks for OAuth starts a sign-in instead: `202` with its page."""
    url = server_url(payload.url)
    plugin_id = custom_plugin_id(payload.name)
    if await transact(session, lambda s: s.get(InstalledPlugin, plugin_id)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "plugin_name_taken",
                "message": f"A plugin named {payload.name} is already connected.",
                "name": payload.name,
            },
        )

    taken = await transact(session, connected_name, url)
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "plugin_already_connected",
                "message": f"This server is already connected as {taken}.",
                "name": taken,
            },
        )
    if needs_https(url):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_needs_https",
                "message": "A plugin's server must use HTTPS, unless it runs on this computer.",
            },
        )
    refusal = await transact(session, refused_hosts, [url_host(url)])
    if refusal is not None:
        raise refusal

    source = RemoteMcpSource(url, token_headers(payload.token))
    try:
        tools = await source.list_tools()
    except ServerError as error:
        sign_in = (
            await start_sign_in(
                session,
                request,
                PluginDraft(
                    plugin_id=plugin_id,
                    name=payload.name,
                    url=url,
                    source=PluginSource.CUSTOM,
                    entry={
                        "name": payload.name,
                        "hosts": [url_host(url)],
                        "auth": {"type": "oauth"},
                    },
                ),
            )
            if error.status == 401 and not payload.token
            else None
        )
        if sign_in is None:
            raise connect_refusal(error) from error
        response.status_code = status.HTTP_202_ACCEPTED
        return sign_in

    def store(s):
        plugin = store_custom_plugin(
            s, plugin_id, payload.name, url, payload.token, tools
        )
        return read_plugin(s, plugin)

    return await transact(session, store)


@router.get(
    "/first-party",
    response_model=list[FirstPartyEntryRead],
    summary="List SurfSense's own plugins",
)
def list_first_party(session: SessionDep) -> list[FirstPartyEntryRead]:
    return read_first_party(session)


@router.get(
    "/first-party/icons/{plugin_id}", summary="One of SurfSense's plugins' icon"
)
def first_party_icon_file(plugin_id: str) -> Response:
    """Packaged beside the list, so served with no network."""
    path = first_party_icon(plugin_id)
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} has no icon")
    return icon_response(path)


@router.post(
    "/first-party/{plugin_id}",
    response_model=PluginRead,
    status_code=status.HTTP_201_CREATED,
    summary="Connect one of SurfSense's own plugins",
)
async def connect_first_party(plugin_id: str, session: SessionDep) -> PluginRead:
    """A refused license still connects: the plugin's status says what is missing."""
    entry = next((e for e in first_party_entries() if e.id == plugin_id), None)
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

    headers = (
        await transact(session, license_headers, entry.url)
        if entry.auth.type == LICENSE
        else {}
    )
    source = RemoteMcpSource(entry.url, headers)
    try:
        listed = await source.list_tools()
    except ServerError as error:
        if check_failure(error) == CheckFailure.UNREACHABLE:
            raise connect_refusal(error) from error
        listed = error
    finally:
        await source.close()

    def store(s):
        return read_plugin(s, store_first_party_plugin(s, entry, listed))

    return await transact(session, store)


@router.post(
    "/{plugin_id}/check",
    response_model=PluginRead,
    summary="List a plugin's server again",
)
async def check_plugin(plugin_id: str, session: SessionDep) -> PluginRead:
    """Records what the server lists now, or why it could not be listed."""

    def address(s):
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None or plugin.disconnected_at is not None:
            return plugin
        return plugin.url, sign_in_headers(s, plugin)

    found = await transact(session, address)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    if isinstance(found, InstalledPlugin):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "plugin_disconnected",
                "message": "Connect this plugin before checking it.",
            },
        )
    listed = await list_once(*found)
    listed = await listed_after_refresh(session, plugin_id, found[1], listed)

    def record(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        record_check(s, plugin, listed)
        return read_plugin(s, plugin)

    return await transact(session, record)


@router.put(
    "/{plugin_id}/key", response_model=PluginRead, summary="Replace a plugin's key"
)
async def write_key(
    plugin_id: str, payload: KeyWrite, session: SessionDep
) -> PluginRead:
    """The server lists its tools with the new key first; a key it refuses is not saved."""
    url = await transact(
        session, lambda s: getattr(s.get(InstalledPlugin, plugin_id), "url", None)
    )
    if url is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    source = RemoteMcpSource(url, token_headers(payload.token))
    try:
        tools = await source.list_tools()
    except ServerError as error:
        raise connect_refusal(error) from error
    finally:
        await source.close()

    def store(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        replace_key(s, plugin, payload.token, tools)
        return read_plugin(s, plugin)

    return await transact(session, store)


@router.put(
    "/{plugin_id}/tools/{tool}", response_model=PluginRead, summary="Switch a tool"
)
def write_tool(
    plugin_id: str, tool: str, payload: ToolWrite, session: SessionDep
) -> PluginRead:
    row = set_tool(
        session, plugin_id, tool, enabled=payload.enabled, approval=payload.approval
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{plugin_id} has no tool {tool}"
        )
    return read_plugin(session, session.get_one(InstalledPlugin, plugin_id))


@router.get(
    "/third-party",
    response_model=ThirdPartyAllowed,
    summary="Whether third-party plugins are allowed",
)
def read_third_party(session: SessionDep) -> ThirdPartyAllowed:
    return ThirdPartyAllowed(allowed=third_party_on(session))


@router.put(
    "/third-party", status_code=204, summary="Allow or refuse third-party plugins"
)
def write_third_party(payload: ThirdPartyAllowed, session: SessionDep) -> None:
    set_third_party_on(session, payload.allowed)


@router.put("/{plugin_id}", response_model=PluginRead, summary="Switch a plugin")
def write_plugin(
    plugin_id: str, payload: PluginWrite, session: SessionDep
) -> PluginRead:
    plugin = set_plugin_enabled(session, plugin_id, payload.enabled)
    if plugin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    return read_plugin(session, plugin)


@router.post(
    "/{plugin_id}/disconnect",
    response_model=PluginRead,
    summary="Disconnect a plugin, keeping it and its tool settings",
)
def disconnect_plugin(plugin_id: str, session: SessionDep) -> PluginRead:
    plugin = disconnect(session, plugin_id)
    if plugin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    return read_plugin(session, plugin)


@router.post(
    "/{plugin_id}/connect",
    response_model=PluginRead,
    summary="Connect a disconnected plugin that needs nothing entered",
)
async def connect_plugin(plugin_id: str, session: SessionDep) -> PluginRead:
    """A key or an account sign-in comes back through `/key` or `/sign-in` instead.

    As at first connect, only an unreachable server refuses; a refused license connects
    with its reason as the status.
    """

    def address(s):
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None:
            return None
        return plugin.credential_kind, plugin.url, sign_in_headers(s, plugin)

    found = await transact(session, address)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    kind, url, headers = found
    if kind == "token":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "plugin_needs_key", "message": "Enter the plugin's key."},
        )
    if kind == OAUTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_needs_account",
                "message": "Sign in to the plugin with your account.",
            },
        )
    source = RemoteMcpSource(url, headers)
    try:
        listed = await source.list_tools()
    except ServerError as error:
        if check_failure(error) == CheckFailure.UNREACHABLE:
            raise connect_refusal(error) from error
        listed = error
    finally:
        await source.close()

    def store(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        plugin.disconnected_at = None
        record_check(s, plugin, listed)
        return read_plugin(s, plugin)

    return await transact(session, store)


@router.delete(
    "/{plugin_id}", status_code=204, summary="Remove a plugin and its tool settings"
)
def remove_plugin(plugin_id: str, session: SessionDep) -> None:
    if not remove(session, plugin_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
