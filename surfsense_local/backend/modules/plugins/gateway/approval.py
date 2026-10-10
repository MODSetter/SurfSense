"""Whether a tool must be approved before each call, from its annotations and the user's setting.

A server's annotations are its own claim, so a read-only tool skips approval only on a
plugin SurfSense runs, as Claude's connectors trust a read-only annotation.
"""

from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval


def needs_approval(tool: ReadyTool) -> bool:
    read_only = tool.annotations.get("readOnlyHint") is True
    if read_only and tool.plugin_source == PluginSource.FIRST_PARTY:
        return False
    # MCP's default for a tool that says nothing: it may destroy.
    destructive = (
        not read_only and tool.annotations.get("destructiveHint", True) is True
    )
    return destructive or tool.approval != ToolApproval.ALWAYS
