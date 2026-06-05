"""Cross-agent shared tools and tool metadata.

Tool *implementations* live with the agents that own them (e.g. deliverable
generators and their knowledge-base search helper under
``subagents/builtins/deliverables/tools``). This package holds only the
genuinely shared piece: the display-metadata catalog.
"""

from .catalog import TOOL_CATALOG, ToolMetadata

__all__ = [
    "TOOL_CATALOG",
    "ToolMetadata",
]
