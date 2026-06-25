"""Rewrite model ``[n]`` citations into frontend ``[citation:<payload>]`` markers.

The model cites with tiny ordinals ``[n]`` — one per bracket. Several citations
are just several brackets (``[1][2]`` or ``[1], [2]``). Each ordinal is resolved
through the registry and replaced with a marker the citation renderer
understands. Unknown or not-yet-renderable ordinals are dropped, so a bad
citation disappears rather than misleads. Code spans are left untouched.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .markers import to_frontend_payload
from .registry import CitationRegistry

# Fenced (```...```) and inline (`...`) code; mirrors the frontend's single
# code-region pattern so ordinals inside examples are never rewritten.
_CODE_REGION = re.compile(r"```[\s\S]*?```|`[^`\n]+`")

# A single ordinal in a bracket: `[1]`, `[12]`. We deliberately match even when
# glued to the preceding word (`docs[17]`) because the model very frequently
# writes citations that way — requiring a non-word char before `[` (to dodge
# `arr[1]`) silently dropped those citations, leaving raw `[n]` that both fails to
# render and reads like array indexing. Genuine code/array syntax is instead
# protected by the code-region carve-out below; an unresolved ordinal drops
# harmlessly. Adjacent citations `[1][2]` are each rewritten.
_ORDINAL = re.compile(r"\[\s*(\d+)\s*\]")


def normalize_citations(text: str, registry: CitationRegistry) -> str:
    """Replace each ``[n]`` with its resolved marker; drop the unresolved."""
    if not text:
        return text

    rewrite = _ordinal_rewriter(registry)
    return _outside_code(text, lambda span: _ORDINAL.sub(rewrite, span))


def _ordinal_rewriter(registry: CitationRegistry) -> Callable[[re.Match[str]], str]:
    """Build the substitution that turns one ordinal into a marker (or drops it)."""

    def rewrite(match: re.Match[str]) -> str:
        entry = registry.resolve(int(match.group(1)))
        payload = to_frontend_payload(entry) if entry else None
        return f"[citation:{payload}]" if payload is not None else ""

    return rewrite


def _outside_code(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` to non-code spans only; code regions pass through verbatim."""
    parts = []
    last = 0
    for region in _CODE_REGION.finditer(text):
        parts.append(transform(text[last : region.start()]))
        parts.append(region.group(0))
        last = region.end()
    parts.append(transform(text[last:]))
    return "".join(parts)


__all__ = ["normalize_citations"]
