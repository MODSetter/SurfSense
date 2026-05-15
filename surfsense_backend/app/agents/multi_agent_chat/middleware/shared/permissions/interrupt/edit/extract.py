"""Extract edited args from a permission decision payload.

Two shapes are accepted (mirrors :func:`app.agents.new_chat.tools.hitl._parse_decision`):

- LangChain HITL envelope: ``{"edited_action": {"args": {...}}}``.
- Legacy flat shape: ``{"args": {...}}``.

Returns ``None`` when no edited args are present. The orchestrator decides
whether to merge them (see :mod:`interrupt.edit.merge`); this module is pure parsing.
"""

from __future__ import annotations

from typing import Any


def extract_edited_args(decision_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(decision_payload, dict):
        return None

    edited_action = decision_payload.get("edited_action")
    if isinstance(edited_action, dict):
        edited_args = edited_action.get("args")
        if isinstance(edited_args, dict):
            return edited_args

    flat_args = decision_payload.get("args")
    if isinstance(flat_args, dict):
        return flat_args

    return None


__all__ = ["extract_edited_args"]
