"""Self-gated approval primitive — tools that pause from inside their own body.

Public surface:
- :func:`request_approval` — entry point for sensitive tool bodies.
- :class:`HITLResult` — outcome contract.
- ``DEFAULT_AUTO_APPROVED_TOOLS`` — safe-by-construction allowlist.
"""

from .auto_approved import DEFAULT_AUTO_APPROVED_TOOLS
from .request import request_approval
from .result import HITLResult

__all__ = [
    "DEFAULT_AUTO_APPROVED_TOOLS",
    "HITLResult",
    "request_approval",
]
