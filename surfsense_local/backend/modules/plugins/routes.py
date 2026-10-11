"""The `/plugins` routes: connecting, listing and switching plugins, the same for every kind."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.dependencies import SessionDep, transact
from modules.plugins.installed.custom_plugin import (
    connected_name,
    custom_plugin_id,
    store_custom_plugin,
    url_host,
)
from modules.plugins.installed.disconnect import disconnect
from modules.plugins.installed.https_required import needs_https
from modules.plugins.installed.models import InstalledPlugin, ToolApproval
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.installed.plugin_read import PluginRead, read_plugin, read_plugins
from modules.plugins.installed.plugin_switch import set_plugin_enabled
from modules.plugins.installed.server_url import server_url
from modules.plugins.installed.third_party import set_third_party_on, third_party_on
from modules.plugins.installed.tool_settings import set_tool
from modules.plugins.remote.connect_refusal import connect_refusal
from modules.plugins.remote.mcp_client.server_error import ServerError
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


class CustomPluginWrite(BaseModel):
    url: str
    name: str
    token: str | None = None


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
        raise connect_refusal(error) from error

    def store(s):
        plugin = store_custom_plugin(
            s, plugin_id, payload.name, url, payload.token, tools
        )
        return read_plugin(s, plugin)

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
        return (
            None if plugin is None else (plugin.url, token_headers(plugin.credential))
        )

    found = await transact(session, address)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
    source = RemoteMcpSource(*found)
    try:
        listed = await source.list_tools()
    except ServerError as error:
        listed = error
    finally:
        await source.close()

    def record(s):
        plugin = s.get_one(InstalledPlugin, plugin_id)
        record_check(s, plugin, listed)
        return read_plugin(s, plugin)

    return await transact(session, record)


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


@router.delete("/{plugin_id}", status_code=204, summary="Disconnect a plugin")
def remove_plugin(plugin_id: str, session: SessionDep) -> None:
    if not disconnect(session, plugin_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
