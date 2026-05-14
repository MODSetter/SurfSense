"""Self-gated approval primitive — tools that pause from inside their own body.

Public surface:
- :func:`request_approval` — entry point for sensitive tool bodies.
- :func:`self_gated_tool_permission_row` — build an allow/ask row for a self-gated tool.
- :class:`HITLResult` — outcome contract.
- ``DEFAULT_AUTO_APPROVED_TOOLS`` — safe-by-construction allowlist.
"""

from .auto_approved import DEFAULT_AUTO_APPROVED_TOOLS
from .request import request_approval
from .result import HITLResult
from .tool_row import self_gated_tool_permission_row

__all__ = [
    "DEFAULT_AUTO_APPROVED_TOOLS",
    "HITLResult",
    "request_approval",
    "self_gated_tool_permission_row",
]
