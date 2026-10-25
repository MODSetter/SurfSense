"""Where the registry comes from: the repository in development, the plugin host when packaged."""

import sys
from pathlib import Path

# surfsense_local/backend/modules/plugins/lists/registry/ -> the repository root.
REPOSITORY_REGISTRY = (
    Path(__file__).resolve().parents[6] / "backend" / "plugins" / "registry"
)


def reads_repository() -> bool:
    """Unpackaged, the checkout's registry is trusted as it stands, unsigned."""
    return not getattr(sys, "frozen", False)
