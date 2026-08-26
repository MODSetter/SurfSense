"""No-op span used when telemetry is disabled (avoids per-call None checks)."""

from __future__ import annotations

from typing import Any


class NoopSpan:
    """Stand-in mimicking the subset of ``Span`` callers use."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        return None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None
