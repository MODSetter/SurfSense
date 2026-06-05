"""SurfSense filesystem middleware (multi-agent flavour)."""

from __future__ import annotations

from .index import build_filesystem_mw
from .middleware import SurfSenseFilesystemMiddleware

__all__ = [
    "SurfSenseFilesystemMiddleware",
    "build_filesystem_mw",
]
