"""The `/plugins` routes: connecting, listing and switching plugins, the same for every kind."""

from fastapi import APIRouter, HTTPException, Response, status
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
from modules.plugins.installed.replace_headers import replace_headers
from modules.plugins.installed.server_url import server_url
from modules.plugins.installed.third_party import set_third_party_on, third_party_on
from modules.plugins.installed.third_party_off import (
    plugin_third_party_refusal,
    third_party_refusal,
)
from modules.plugins.installed.tool_settings import set_tool
from modules.plugins.lists.first_party.entry_read import (
    FirstPartyEntryRead,
    read_first_party,
)
from modules.plugins.lists.first_party.first_party_icon import first_party_icon
from modules.plugins.lists.first_party.first_party_list import first_party_entries
from modules.plugins.lists.icon_response import icon_response
from modules.plugins.lists.list_entry import EntryAuth
from modules.plugins.lists.registry.entry_headers import filled_headers
from modules.plugins.remote.connect_refusal import connect_refusal
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.moved_from_sse import keep_address, listed_where_it_moved
from modules.plugins.remote.sign_in.headers.given_headers import (
    as_sent,
    given_headers,
)
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.headers.headers_credential import HEADERS
from modules.plugins.remote.sign_in.oauth.listed_after_refresh import (
    list_once,
    listed_after_refresh,
)
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.start_sign_in import (
    SignInsDep,
    save_for_sign_in,
)
from modules.plugins.remote.sign_in.plugin_headers import (
    LICENSE,
    license_headers,
    sign_in_headers,
)
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.source import RemoteMcpSource
from modules.plugins.remote.streamable_only import listed_streamable

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _read_by_id(session, plugin_id: str) -> PluginRead:
    return read_plugin(session, session.get_one(InstalledPlugin, plugin_id))


def _named_headers(session, plugin_id: str):
    """A plugin's URL, and the headers its registry entry names, if it names any."""
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is None:
        return None
    auth = plugin.entry.get("auth") or {}
    named = (
        EntryAuth.model_validate(auth).headers
        if plugin.source == PluginSource.REGISTRY and auth.get("type") == HEADERS
        else None
    )
    return plugin.url, named


def _address(session, plugin_id: str):
    """A connected plugin's URL, or None."""
    plugin = session.get(InstalledPlugin, plugin_id)
    return None if plugin is None else plugin.url


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
    # Any key, in whichever headers the server reads; `token` is one Bearer header.
    headers: list[SignInHeader] | None = None
    token: str | None = None


class HeadersWrite(BaseModel):
    headers: list[SignInHeader]


@router.get("", response_model=list[PluginRead], summary="List connected plugins")
def list_plugins(session: SessionDep) -> list[PluginRead]:
    return read_plugins(session)


@router.post(
    "/custom",
    response_model=PluginRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a remote server by URL",
)
async def add_custom_plugin(
    payload: CustomPluginWrite, session: SessionDep
) -> PluginRead:
    """A server whose refusal asks for OAuth is saved signed out, to Connect from its row."""
    refusal = await transact(session, third_party_refusal, PluginSource.CUSTOM)
    if refusal is not None:
        raise refusal
    headers = given_headers(payload.headers, payload.token)
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

    try:
        tools = await listed_streamable(url, as_sent(headers))
    except ServerError as error:
        # A server asking for an account is saved, signed out, for Connect on its row.
        draft = PluginDraft(
            plugin_id=plugin_id,
            name=payload.name,
            url=url,
            source=PluginSource.CUSTOM,
            entry={
                "name": payload.name,
                "hosts": [url_host(url)],
                "auth": {"type": "oauth"},
            },
        )
        if (
            error.status == 401
            and not headers
            and await save_for_sign_in(session, draft)
        ):
            return await transact(session, _read_by_id, plugin_id)
        raise connect_refusal(error) from error

    def store(s):
        plugin = store_custom_plugin(s, plugin_id, payload.name, url, headers, tools)
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
    refusal = await transact(session, plugin_third_party_refusal, plugin_id)
    if refusal is not None:
        raise refusal

    def address(s):
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None or plugin.disconnected_at is not None:
            return plugin
        return plugin.url, sign_in_headers(s, plugin), dict(plugin.entry)

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
    url, headers, entry = found
    listed = await list_once(url, headers)
    listed = await listed_after_refresh(session, plugin_id, headers, listed)
    url, listed = await listed_where_it_moved(entry, url, headers, listed)

    def record(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        keep_address(s, plugin, url)
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
    refusal = await transact(session, plugin_third_party_refusal, plugin_id)
    if refusal is not None:
        raise refusal
    address = await transact(session, _address, plugin_id)
    if address is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    source = RemoteMcpSource(address, token_headers(payload.token))
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
    "/{plugin_id}/headers",
    response_model=PluginRead,
    summary="Replace the headers a plugin signs in with",
)
async def write_headers(
    plugin_id: str, payload: HeadersWrite, session: SessionDep
) -> PluginRead:
    """The server lists its tools with the new headers first; ones it refuses are not saved.

    A registry plugin's go only in the headers its entry names, with their prefixes.
    """
    refusal = await transact(session, plugin_third_party_refusal, plugin_id)
    if refusal is not None:
        raise refusal
    found = await transact(session, _named_headers, plugin_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    url, named = found
    headers = (
        filled_headers(named, payload.headers)
        if named is not None
        else given_headers(payload.headers) or []
    )
    source = RemoteMcpSource(url, as_sent(headers))
    try:
        tools = await source.list_tools()
    except ServerError as error:
        raise connect_refusal(error) from error
    finally:
        await source.close()

    def store(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        replace_headers(s, plugin, headers, tools)
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
def write_third_party(
    payload: ThirdPartyAllowed, session: SessionDep, sign_ins: SignInsDep
) -> None:
    set_third_party_on(session, payload.allowed)
    if not payload.allowed:
        sign_ins.cancel_third_party()


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
    """A key or an account sign-in comes back through `/key`, `/headers` or `/sign-in` instead.

    As at first connect, only an unreachable server refuses; a refused license connects
    with its reason as the status.
    """
    refusal = await transact(session, plugin_third_party_refusal, plugin_id)
    if refusal is not None:
        raise refusal

    def address(s):
        plugin = s.get(InstalledPlugin, plugin_id)
        if plugin is None:
            return None
        return (
            plugin.credential_kind,
            plugin.url,
            sign_in_headers(s, plugin),
        )

    found = await transact(session, address)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    kind, url, headers = found
    if kind in ("token", HEADERS):
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
