"""One tool call to SurfSense's plugin, read for its items whole, not the text cut at 32 KB."""

from typing import Any

from modules.documents.web_sources.plugin_calls.plugin_access import (
    MISSING_LICENSE,
    LicenseRefusedError,
    PluginAccess,
)
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.session import McpSession


class PluginUnavailableError(Exception):
    """The plugin host could not be reached, or failed."""


class ToolRefusedError(Exception):
    """The tool ran and answered with an error, such as no page it could read."""


async def call_plugin(
    access: PluginAccess, tool: str, arguments: dict[str, Any], read_seconds: float
) -> list[dict[str, Any]]:
    try:
        result = await McpSession(access.url, access.headers).call_tool(
            tool, arguments, read_seconds
        )
    except ServerError as error:
        if error.status in (401, 403):
            raise LicenseRefusedError(error.reason or MISSING_LICENSE) from error
        raise PluginUnavailableError(str(error)) from error
    if result.is_error:
        texts = [getattr(block, "text", "") for block in result.content]
        raise ToolRefusedError(" ".join(text for text in texts if text))
    structured = result.structured_content
    items = structured.get("items") if isinstance(structured, dict) else None
    return [item for item in items or [] if isinstance(item, dict)]
