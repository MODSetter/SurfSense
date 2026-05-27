"""``agent_task`` action: spin up multi_agent_chat for one rendered query.

Imports ``definition`` for its side-effect (self-registration on the actions
registry) and re-exports ``build_handler`` for direct consumers.
"""

from __future__ import annotations

from .factory import build_handler
from .params import AgentTaskActionParams

__all__ = ["AgentTaskActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: E402, F401
