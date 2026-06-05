"""Cross-package agent contracts.

Symbols here are intentionally framework-light (no LangGraph / deepagents
internals) so they can be imported from both ``app.agents.new_chat`` and
``app.agents.chat.multi_agent_chat`` without creating a circular dependency
between the two packages. See ``receipt.py`` for the rationale.
"""

from __future__ import annotations
