"""Pattern-based allow/deny/ask middleware with HITL fallback (vertical slice).

Public surface (one entry point only — every other symbol is an internal of
the rule engine and stays inside ``middleware/``, ``ask/``, or ``deny.py``):

- :func:`build_permission_mw` — construction recipe shared by every stack.
"""

from .middleware.factory import build_permission_mw

__all__ = ["build_permission_mw"]
