"""Route-local FS tool policy.

The KB subagent's actual ``BaseTool`` instances are provided at runtime by
``SurfSenseFilesystemMiddleware`` (mounted in ``agent.py``). This module
only carries the *names* of destructive ops so the agent can convert them
into permission rules — see :data:`KB_RULESET` in ``agent.py``.
"""

from __future__ import annotations

DESTRUCTIVE_FS_OPS: tuple[str, ...] = (
    "rm",
    "rmdir",
    "move_file",
    "edit_file",
    "write_file",
)


__all__ = ["DESTRUCTIVE_FS_OPS"]
