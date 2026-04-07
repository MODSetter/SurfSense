"""Agent-based vision autocomplete with scoped filesystem exploration."""

from app.agents.autocomplete.autocomplete_agent import (
    create_autocomplete_agent,
    stream_autocomplete_agent,
)

__all__ = [
    "create_autocomplete_agent",
    "stream_autocomplete_agent",
]
