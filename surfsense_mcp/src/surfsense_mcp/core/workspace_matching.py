"""Resolve a user-supplied workspace reference to a single workspace.

Pure matching over an already-fetched list: name (exact, then case-insensitive,
then unique substring) or numeric id. Kept apart from WorkspaceContext so the
resolution rules can be read and tested without the network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import ToolError

if TYPE_CHECKING:
    from .workspace_context import Workspace


def match_by_name(reference: str, workspaces: list[Workspace]) -> Workspace:
    """Match on name: exact, then case-insensitive, then unique substring."""
    needle = reference.strip()
    exact = [w for w in workspaces if w.name == needle]
    if exact:
        return exact[0]
    lowered = needle.casefold()
    insensitive = [w for w in workspaces if w.name.casefold() == lowered]
    if insensitive:
        return insensitive[0]
    partial = [w for w in workspaces if lowered in w.name.casefold()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ToolError(
            f"'{reference}' matches several workspaces: {name_list(partial)}. "
            "Use a more specific name or the id."
        )
    raise ToolError(
        f"No workspace named '{reference}'. Available: {name_list(workspaces)}."
    )


def as_int(reference: str | int) -> int | None:
    """Return the reference as an id, or None when it isn't numeric."""
    if isinstance(reference, int):
        return reference
    text = reference.strip()
    return int(text) if text.isdigit() else None


def name_list(workspaces: list[Workspace]) -> str:
    """Render workspaces as a human-readable 'name (id N)' list."""
    return ", ".join(f"{w.name} (id {w.id})" for w in workspaces)
