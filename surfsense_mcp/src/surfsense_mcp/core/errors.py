"""The single failure type tools raise to speak plainly to the model.

A failed tool call should tell the model what to do next, not leak a stack
trace. Anything the caller could act on — no workspace selected, an unknown id,
a rejected request — is raised as ``ToolError`` with a sentence safe to surface.
"""

from __future__ import annotations


class ToolError(Exception):
    """A user-actionable failure whose message is meant for the model to read."""
