"""Route-local FS tool policy.

The KB subagent's actual ``BaseTool`` instances are provided at runtime by
``SurfSenseFilesystemMiddleware`` (mounted in ``agent.py``). This module only
carries policy that the subagent spec needs to declare up front — which
destructive ops require explicit user confirmation via ``interrupt_on``.

Mirrors the ``desktop_safety`` ruleset in
``multi_agent_chat.middleware.shared.permissions.context``: in desktop mode
those rules guard the main-agent FS toolset; in cloud mode the same toolset
lives on the KB subagent and the same policy is enforced here instead.
"""

from __future__ import annotations

DESTRUCTIVE_FS_OPS: tuple[str, ...] = (
    "rm",
    "rmdir",
    "move_file",
    "edit_file",
    "write_file",
)


def destructive_fs_interrupt_on() -> dict[str, bool]:
    """Fresh ``interrupt_on`` dict for the KB subagent spec."""
    return {op: True for op in DESTRUCTIVE_FS_OPS}


__all__ = ["DESTRUCTIVE_FS_OPS", "destructive_fs_interrupt_on"]
