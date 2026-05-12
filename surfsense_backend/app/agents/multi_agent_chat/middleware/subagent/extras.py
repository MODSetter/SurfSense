"""Extra middleware threaded into every registry subagent's stack.

Registry subagents are scoped to one domain (deliverables, research, memory,
connectors, MCP) and never read or write the SurfSense filesystem — that
capability belongs to the ``knowledge_base`` subagent. Keeping FS off the
registry stacks avoids polluting their tool surface with FS tools they
never act on.
"""

from __future__ import annotations

from typing import Any

from ..shared.resilience import ResilienceBundle
from ..shared.todos import build_todos_mw


def build_subagent_extras(
    *,
    resilience: ResilienceBundle,
) -> list[Any]:
    extras: list[Any] = [build_todos_mw()]
    extras.extend(resilience.as_list())
    return extras
