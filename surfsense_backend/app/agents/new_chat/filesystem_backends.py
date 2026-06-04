"""Backward-compatible shim.

Moved to ``app.agents.shared.filesystem_backends``. Re-exported here for the
frozen single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.filesystem_backends import build_backend_resolver

__all__ = ["build_backend_resolver"]
