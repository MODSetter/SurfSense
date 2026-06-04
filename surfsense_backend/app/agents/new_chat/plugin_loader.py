"""Backward-compatible shim.

Moved to ``app.agents.shared.plugin_loader``. Re-exported here for the frozen
single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.plugin_loader import (
    PLUGIN_ENTRY_POINT_GROUP,
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)

__all__ = [
    "PLUGIN_ENTRY_POINT_GROUP",
    "PluginContext",
    "load_allowed_plugin_names_from_env",
    "load_plugin_middlewares",
]
