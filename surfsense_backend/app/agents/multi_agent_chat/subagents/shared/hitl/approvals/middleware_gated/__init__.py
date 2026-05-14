"""Middleware-gated approval primitives — interception via langchain middlewares.

Public surface:
- :func:`middleware_gated_tool_permission_row` — tag a tool's row for interception.
- :func:`middleware_gated_interrupt_on` — build the ``interrupt_on`` map fed
  into ``HumanInTheLoopMiddleware``.

The actual ``HumanInTheLoopMiddleware`` and ``PermissionMiddleware`` instances
that consume these helpers live under
``middleware/shared/permissions/`` (rule-engine slice).
"""

from .interrupt_on import middleware_gated_interrupt_on
from .tool_row import middleware_gated_tool_permission_row

__all__ = [
    "middleware_gated_interrupt_on",
    "middleware_gated_tool_permission_row",
]
