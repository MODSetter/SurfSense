"""What a model can be asked to do in a request, for choosing an agent loop.

None is not no. models.dev omits `structured_output` on 2,442 models while
writing `false` on 739 others, and reports `limit.context` as 0 on entries
that are not token models. Both become None, and the caller decides.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["Supports", "supports"]


@dataclass(frozen=True)
class Supports:
    """Request features a model accepts. None means models.dev never said."""

    tool_call: bool
    reasoning: bool
    structured_output: bool | None
    context_window: int | None


def supports(entry: Mapping[str, Any]) -> Supports:
    """Read the request features off a models.dev entry."""
    context = (entry.get("limit") or {}).get("context")
    return Supports(
        tool_call=bool(entry.get("tool_call")),
        reasoning=bool(entry.get("reasoning")),
        structured_output=entry.get("structured_output"),
        context_window=context if isinstance(context, int) and context > 0 else None,
    )
