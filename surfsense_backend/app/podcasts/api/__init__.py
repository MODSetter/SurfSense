"""HTTP API for the podcast lifecycle.

The router is mounted at cutover (replacing the legacy podcast routes); it is
kept separate here so it can be wired in one step without colliding with the old
routes during parallel development.
"""

from __future__ import annotations

from .routes import router

__all__ = ["router"]
