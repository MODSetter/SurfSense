"""Cross-agent shared tools and tool metadata.

Tool *implementations* live with the agents that own them (e.g. deliverable
generators under ``subagents/builtins/deliverables/tools``). This package
holds only the genuinely shared pieces: the display-metadata catalog and the
knowledge-base helpers used across agents.
"""

from .catalog import TOOL_CATALOG, ToolMetadata
from .knowledge_base import (
    CONNECTOR_DESCRIPTIONS,
    format_documents_for_context,
    search_knowledge_base_async,
)

__all__ = [
    # Tool catalog (display metadata)
    "TOOL_CATALOG",
    "ToolMetadata",
    # Knowledge base utilities
    "CONNECTOR_DESCRIPTIONS",
    "format_documents_for_context",
    "search_knowledge_base_async",
]
