"""Connection-scoped remote model discovery and persistence."""

from modules.llm.connections.service import (
    DiscoveredModel,
    discover_models,
    normalize_base_url,
    probe_connection,
)

__all__ = [
    "DiscoveredModel",
    "discover_models",
    "normalize_base_url",
    "probe_connection",
]
