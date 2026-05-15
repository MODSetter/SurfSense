"""Build the ``permission_ask`` interrupt payload (pure data).

The frontend's streaming layer keys off ``type`` and renders the approval
card from ``action`` (the tool call being reviewed) and ``context``
(the matched rules and patterns that prompted the ask). ``context.always``
lists the patterns the user can promote to a permanent allow rule with a
single ``"always"`` reply.
"""

from __future__ import annotations

from typing import Any

from app.agents.new_chat.permissions import Rule


def build_permission_ask_payload(
    *,
    tool_name: str,
    args: dict[str, Any],
    patterns: list[str],
    rules: list[Rule],
) -> dict[str, Any]:
    return {
        "type": "permission_ask",
        # ``params`` (not ``args``) is what SurfSense's streaming normalizer forwards.
        "action": {"tool": tool_name, "params": args or {}},
        "context": {
            "patterns": patterns,
            "rules": [
                {
                    "permission": r.permission,
                    "pattern": r.pattern,
                    "action": r.action,
                }
                for r in rules
            ],
            "always": patterns,
        },
    }


__all__ = ["build_permission_ask_payload"]
