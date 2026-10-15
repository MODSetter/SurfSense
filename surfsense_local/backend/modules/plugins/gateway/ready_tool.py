"""A tool ready to be called, as every caller sees it: engine-neutral."""

from dataclasses import dataclass
from typing import Any

from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure


@dataclass(frozen=True)
class ReadyTool:
    qualified_name: str
    plugin_id: str
    plugin_name: str
    plugin_source: PluginSource
    tool: str
    title: str | None
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    approval: ToolApproval
    exposure: ToolExposure
