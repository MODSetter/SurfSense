"""
Context schema definitions for SurfSense agents.

This module defines the per-invocation context object passed to the SurfSense
deep agent via ``agent.astream_events(..., context=ctx)`` (LangGraph >= 0.6).

The agent's compiled graph is the same across invocations (and cached by
``agent_cache``), so anything that varies per turn — the user mentions a
specific document, the front-end issues a unique ``request_id``, etc. —
MUST live on this context object instead of being captured into a
middleware ``__init__`` closure. Middlewares read fields back via
``runtime.context.<field>``; tools read them via ``runtime.context``.

This object is read inside both ``KnowledgePriorityMiddleware`` (for
``mentioned_document_ids``) and any future middleware that needs
per-request state without invalidating the compiled-agent cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class FileOperationContractState(TypedDict):
    intent: str
    confidence: float
    suggested_path: str
    timestamp: str
    turn_id: str


@dataclass
class SurfSenseContextSchema:
    """
    Per-invocation context for the SurfSense deep agent.

    Defaults are chosen so the dataclass can be safely default-constructed
    (LangGraph's ``Runtime.context`` itself defaults to ``None`` if no
    context is supplied — see ``langgraph.runtime.Runtime``). All fields
    are optional; consumers must None-check before reading.

    Phase 1.5 fields:
        search_space_id: Search space the request is scoped to.
        mentioned_document_ids: KB documents the user @-mentioned this turn.
            Read by ``KnowledgePriorityMiddleware`` to seed its priority
            list. Stays out of the compiled-agent cache key — that's the
            whole point of putting it here.
        file_operation_contract: One-shot file operation contract emitted
            by ``FileIntentMiddleware`` for the upcoming turn.
        turn_id / request_id: Correlation IDs surfaced by the streaming
            task; populated for telemetry.

    Phase 2 will extend with: thread_id, user_id, visibility,
    filesystem_mode, anon_session_id, available_connectors,
    available_document_types, created_by_id (everything currently captured
    by middleware ``__init__`` closures).
    """

    search_space_id: int | None = None
    mentioned_document_ids: list[int] = field(default_factory=list)
    file_operation_contract: FileOperationContractState | None = None
    turn_id: str | None = None
    request_id: str | None = None
