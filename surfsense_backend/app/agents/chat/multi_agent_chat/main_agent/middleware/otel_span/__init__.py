"""OTel-span middleware: spans on model and tool calls (impl + builder)."""

from .builder import build_otel_mw
from .middleware import OtelSpanMiddleware

__all__ = [
    "OtelSpanMiddleware",
    "build_otel_mw",
]
