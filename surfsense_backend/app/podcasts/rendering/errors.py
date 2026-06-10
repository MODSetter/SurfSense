"""Failures raised while rendering a transcript to audio."""

from __future__ import annotations


class RenderError(RuntimeError):
    """Rendering could not produce a final audio file.

    Wraps both per-segment synthesis failures and the merge step so the render
    task sees one failure type regardless of where it originated.
    """
