"""Identity of the agent that emitted a streamed event.

The wire field is ``emitted_by``; the Python identity is :class:`Emitter`.
``EmitterRegistry`` resolves which emitter owns a LangGraph event, with
LangGraph's own namespace metadata as the primary key and a parent_ids
walk as a fallback for cases where context vars don't propagate.
"""

from __future__ import annotations

from .emitter import (
    MAIN_EMITTER,
    Emitter,
    EmitterLevel,
    attach_emitted_by,
    main_emitter,
    subagent_emitter,
)
from .registry import EmitterRegistry

__all__ = [
    "MAIN_EMITTER",
    "Emitter",
    "EmitterLevel",
    "EmitterRegistry",
    "attach_emitted_by",
    "main_emitter",
    "subagent_emitter",
]
