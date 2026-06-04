"""Backward-compatible shim.

Moved to ``app.agents.shared.middleware.scoped_model_fallback``. Re-exported here
for the frozen single-agent stack (``chat_deepagent``).
"""

from app.agents.shared.middleware.scoped_model_fallback import (
    ScopedModelFallbackMiddleware,
)

__all__ = ["ScopedModelFallbackMiddleware"]
