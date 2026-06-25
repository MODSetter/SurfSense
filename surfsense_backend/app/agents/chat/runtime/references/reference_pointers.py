"""Render resolved references into a ``<referenced_this_turn>`` pointer block.

Pointers, not content: each line names what the user referenced and how to
reach it (a path, a connector handle, a title) so the model knows what to
retrieve from. Actual content is pulled later via tools, never injected here.
"""

from __future__ import annotations

from .models import (
    ChatReference,
    ConnectorReference,
    DocumentReference,
    FolderReference,
    Reference,
)

_HEADER = (
    "The user pointed at these with @ this turn. They are scope, not content "
    "— when the question is about them, retrieve from them before answering."
)


def render_reference_pointers(references: list[Reference]) -> str | None:
    """Render references as one read-only pointer block.

    Returns ``None`` when there is nothing to render so callers can skip the
    block entirely.
    """
    if not references:
        return None

    lines = [_render_pointer(reference) for reference in references]
    return (
        "<referenced_this_turn>\n"
        f"{_HEADER}\n"
        + "\n".join(lines)
        + "\n</referenced_this_turn>"
    )


def _render_pointer(reference: Reference) -> str:
    """One ``- {kind} {id} — {handle}`` line, shaped per kind."""
    head = f"- {reference.kind.value} {reference.entity_id} — "
    return head + _handle(reference)


def _handle(reference: Reference) -> str:
    """The human-reachable handle: a path, a connector provider, or a title."""
    label = _clean(reference.label)
    match reference:
        case DocumentReference() | FolderReference():
            return f'"{label}" ({reference.path})'
        case ConnectorReference():
            provider = _clean(reference.provider) if reference.provider else ""
            return f"{provider} ({label})" if provider else label
        case ChatReference():
            return f'"{label}"'


def _clean(text: str) -> str:
    """Collapse whitespace so a title can't break the one-line pointer."""
    return " ".join(text.split())


__all__ = ["render_reference_pointers"]
