"""Pattern-based allow/deny/ask middleware with HITL fallback.

Public surface: :class:`PermissionMiddleware` plus
:func:`normalize_permission_decision` for the streaming layer and the
:data:`PatternResolver` type for callers that register per-tool resolvers.
"""

from .decision import normalize_permission_decision
from .middleware import PermissionMiddleware
from .pattern_resolver import PatternResolver

__all__ = [
    "PatternResolver",
    "PermissionMiddleware",
    "normalize_permission_decision",
]
