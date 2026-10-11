"""The plugins the host serves: each folder with a `server.py`, under the root or `proprietary/`.

Each is its own MCP server at `/<id>/mcp`; one image and one host serve them all.
"""

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from mcp.server.mcpserver import MCPServer

from mcp_server.access import Access

# The host's own folders and the code plugins share, beside the plugins; never a plugin.
RESERVED = frozenset({"host", "mcp_server", "proprietary", "license_check", "scraping"})


@dataclass(frozen=True)
class MountedPlugin:
    id: str
    server: MCPServer
    access: Access | None


def mounted_plugins(root: Path) -> list[MountedPlugin]:
    """Without `proprietary/`, the open build, only the Apache-2.0 plugins."""
    folders = [*root.iterdir()]
    if (root / "proprietary").is_dir():
        folders += (root / "proprietary").iterdir()
    plugins = [
        _mounted(folder)
        for folder in sorted(folders, key=lambda folder: folder.name)
        if folder.name not in RESERVED and (folder / "server.py").is_file()
    ]
    ids = [plugin.id for plugin in plugins]
    if len(set(ids)) != len(ids):
        raise ValueError(f"two plugins share an id: {sorted(ids)}")
    return plugins


def _mounted(folder: Path) -> MountedPlugin:
    module = _loaded(folder / "server.py")
    build: Callable[[], MCPServer] = module.server
    return MountedPlugin(plugin_id(folder), build(), getattr(module, "access", None))


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
