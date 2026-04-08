"""Pre-register the connector_indexers package to bypass a circular import
in its ``__init__.py`` (airtable_indexer -> routes -> connector_indexers).

This lets tests import individual indexer modules (e.g.
``google_drive_indexer``) without triggering the full package init.
"""

import sys
import types
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]


def _stub_package(dotted: str, fs_dir: Path) -> None:
    if dotted not in sys.modules:
        mod = types.ModuleType(dotted)
        mod.__path__ = [str(fs_dir)]
        mod.__package__ = dotted
        sys.modules[dotted] = mod

    parts = dotted.split(".")
    if len(parts) > 1:
        parent_dotted = ".".join(parts[:-1])
        parent = sys.modules.get(parent_dotted)
        if parent is not None:
            setattr(parent, parts[-1], sys.modules[dotted])


_stub_package("app.tasks", _BACKEND / "app" / "tasks")
_stub_package(
    "app.tasks.connector_indexers",
    _BACKEND / "app" / "tasks" / "connector_indexers",
)
