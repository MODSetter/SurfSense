"""Backward-compatible shim.

Moved to ``app.agents.shared.connector_searchable_types``. Re-exported here for
the frozen single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.connector_searchable_types import (
    map_connectors_to_searchable_types,
)

__all__ = ["map_connectors_to_searchable_types"]
