"""Actions domain: registry surface + built-in action packages.

Each action lives in its own subpackage (``agent_task/``, ...) and self-registers
at import time via its ``definition`` module. Side-effect imports below ensure
the registry is populated whenever anyone touches the actions package.
"""

from __future__ import annotations

from .store import all_actions, get_action, register_action
from .types import ActionContext, ActionDefinition, ActionHandler, ActionHandlerFactory

__all__ = [
    "ActionContext",
    "ActionDefinition",
    "ActionHandler",
    "ActionHandlerFactory",
    "all_actions",
    "get_action",
    "register_action",
]

# Built-in actions self-register at import time.
from . import builtin  # noqa: F401
