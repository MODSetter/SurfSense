"""The plugins the host serves: each folder with a `server.py`, under the root or `proprietary/`.

Each is its own MCP server at `/<id>/mcp`; one image and one host serve them all.
"""

import hashlib
import importlib.util
import sys
from collections.abc import Callable, Collection
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from mcp.server.mcpserver import MCPServer

from mcp_server.access import Access

# The host's own folders, the code plugins share, and the host's own routes; never a plugin.
RESERVED = frozenset(
    {
        "host",
        "mcp_server",
        "proprietary",
        "license_check",
        "scraping",
        "health",
        "cancel",
        "license",
        "admin",
        # The license portal's /api/v1.
        "api",
    }
)


# What a plugin keeps from startup to shutdown, such as warm browsers and clients.
Lifespan = Callable[[], AbstractAsyncContextManager[object]]


@dataclass(frozen=True)
class MountedPlugin:
    id: str
    server: MCPServer
    access: Access | None
    # The `lifespan` its `server.py` may define; the host holds it open while it serves.
    lifespan: Lifespan | None = None


def mounted_plugins(
    root: Path, only: Collection[str] | None = None
) -> list[MountedPlugin]:
    """Without `proprietary/`, the open build, only the Apache-2.0 plugins.

    `only` names the plugins this container serves, as one split out of the host does.
    """
    folders = [*root.iterdir()]
    if (root / "proprietary").is_dir():
        folders += (root / "proprietary").iterdir()
    found = sorted(
        (
            folder
            for folder in folders
            if folder.name not in RESERVED and (folder / "server.py").is_file()
        ),
        key=lambda folder: folder.name,
    )
    if only is not None:
        missing = set(only) - {plugin_id(folder) for folder in found}
        if missing:
            raise ValueError(f"PLUGINS names no plugin: {sorted(missing)}")
        found = [folder for folder in found if plugin_id(folder) in only]
    plugins = [_mounted(folder) for folder in found]
    ids = [plugin.id for plugin in plugins]
    if len(set(ids)) != len(ids):
        raise ValueError(f"two plugins share an id: {sorted(ids)}")
    return plugins


def _mounted(folder: Path) -> MountedPlugin:
    module = _loaded(folder / "server.py")
    build: Callable[[], MCPServer] = module.server
    return MountedPlugin(
        plugin_id(folder),
        build(),
        getattr(module, "access", None),
        getattr(module, "lifespan", None),
    )


def plugin_id(folder: Path) -> str:
    """`google_search/` is `google-search`: a package cannot hold a hyphen, nor an id an underscore."""
    return folder.name.replace("_", "-")


def _loaded(path: Path) -> ModuleType:
    # Named by its path, so two roots in one process never share a module.
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
    name = f"_plugin_{path.parent.name}_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
