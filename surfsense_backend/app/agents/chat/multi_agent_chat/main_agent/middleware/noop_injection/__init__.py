"""Noop-injection middleware: provider-compat _noop tool (impl + builder)."""

from .builder import build_noop_injection_mw
from .middleware import NoopInjectionMiddleware

__all__ = [
    "NoopInjectionMiddleware",
    "build_noop_injection_mw",
]
