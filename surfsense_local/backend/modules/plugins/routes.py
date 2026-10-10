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
from modules.plugins.installed.models import InstalledPlugin, ToolApproval
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.installed.plugin_read import PluginRead, read_plugin, read_plugins
from modules.plugins.installed.server_url import server_url
from modules.plugins.installed.third_party import set_third_party_on
from modules.plugins.installed.tool_settings import set_tool
from modules.plugins.remote.connect_refusal import connect_refusal
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.token_headers import token_headers
from modules.plugins.remote.source import RemoteMcpSource

router = APIRouter(prefix="/plugins", tags=["plugins"])


class ToolWrite(BaseModel):
    enabled: bool | None = None
    approval: ToolApproval | None = None


class ThirdPartyWrite(BaseModel):
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
            status.HTTP_409_CONFLICT, f"a plugin named {plugin_id} is connected"
        )

    taken = await transact(session, connected_name, url)
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"This server is already connected as {taken}."
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


@router.put(
    "/third-party", status_code=204, summary="Allow or refuse third-party plugins"
)
def write_third_party(payload: ThirdPartyWrite, session: SessionDep) -> None:
    set_third_party_on(session, payload.allowed)


@router.delete("/{plugin_id}", status_code=204, summary="Disconnect a plugin")
def remove_plugin(plugin_id: str, session: SessionDep) -> None:
    if not disconnect(session, plugin_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{plugin_id} is not connected")
