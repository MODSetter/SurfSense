"""Report writer + section composition primitives. Lazy import."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .writer import write_report

__all__ = ["write_report"]


def __getattr__(name: str):
    if name == "write_report":
        from .writer import write_report

        return write_report
    raise AttributeError(f"module 'surfsense_evals.core.report' has no attribute {name!r}")
