"""Resolved ``@``-references and their pointer block.

References are scope, not content: they tell the model what the user pointed
at this turn so it can retrieve from those sources with tools.
"""

from __future__ import annotations

from .models import ReferenceKind, ResolvedReference
from .reference_pointers import render_reference_pointers

__all__ = [
    "ReferenceKind",
    "ResolvedReference",
    "render_reference_pointers",
]
