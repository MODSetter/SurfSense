"""External LLM providers (used by the native arm).

Lazy imports so the SurfSense-only path doesn't transitively load the
OpenRouter client until something actually constructs ``OpenRouterPdfProvider``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .openrouter_pdf import OpenRouterPdfProvider, OpenRouterResponse

__all__ = ["OpenRouterPdfProvider", "OpenRouterResponse"]


def __getattr__(name: str):
    if name in {"OpenRouterPdfProvider", "OpenRouterResponse"}:
        from . import openrouter_pdf as _mod

        return getattr(_mod, name)
    raise AttributeError(f"module 'surfsense_evals.core.providers' has no attribute {name!r}")
