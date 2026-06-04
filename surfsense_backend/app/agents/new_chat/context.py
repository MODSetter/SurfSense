"""Backward-compatible shim.

The agent context schema moved to :mod:`app.agents.shared.context` as part of
promoting the shared agent toolkit out of ``new_chat`` into the cross-agent
kernel. Import from there directly; this re-export keeps the remaining
importers (the not-yet-retired single-agent stack and the ``new_chat`` package
__init__) working during the migration and will be removed with them.
"""

from __future__ import annotations

from app.agents.shared.context import (
    FileOperationContractState,
    SurfSenseContextSchema,
)

__all__ = [
    "FileOperationContractState",
    "SurfSenseContextSchema",
]
