"""Contribute the ``citation_registry`` state channel to a subagent.

The conversation's ``[n]`` -> source registry lives on graph state behind a
merge reducer (see :mod:`app.agents.chat.multi_agent_chat.shared.state.reducers`).
The orchestrator and the KB subagent get that channel for free via the filesystem
state schema, but a citable subagent that does *not* use the filesystem (e.g.
``research``) still needs the channel declared so its tools can register ``[n]``
via ``Command(update={"citation_registry": ...})`` and have it merge back up.

This middleware adds *only* that channel — no tools, no behavior — so any subagent
that mints citations can opt in without inheriting filesystem semantics.
"""

from __future__ import annotations

from typing import Annotated, NotRequired

from langchain.agents.middleware import AgentMiddleware
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.state.reducers import (
    _citation_registry_merge_reducer,
)


class CitationState(TypedDict):
    """State carrying just the per-conversation ``[n]`` -> source registry."""

    citation_registry: NotRequired[
        Annotated[CitationRegistry, _citation_registry_merge_reducer]
    ]


class CitationStateMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Declare the ``citation_registry`` channel; no tools, no hooks."""

    tools = ()
    state_schema = CitationState


def build_citation_state_mw() -> CitationStateMiddleware:
    return CitationStateMiddleware()


__all__ = [
    "CitationState",
    "CitationStateMiddleware",
    "build_citation_state_mw",
]
