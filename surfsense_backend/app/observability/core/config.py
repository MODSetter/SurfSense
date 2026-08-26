"""Single source of truth for telemetry enablement and env policy."""

from __future__ import annotations

import os

_BOOL_TRUE = {"1", "true", "yes", "on"}

try:
    from opentelemetry import trace as _ot_trace

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _ot_trace = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _BOOL_TRUE


def is_disabled() -> bool:
    """True when SurfSense or OTel's spec kill switch is set."""
    return _env_truthy("SURFSENSE_DISABLE_OTEL") or _env_truthy("OTEL_SDK_DISABLED")


def is_configured() -> bool:
    """True when an OTLP endpoint is wired for this process."""
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    )


def _resolve_enabled() -> bool:
    if not _OTEL_AVAILABLE or is_disabled():
        return False
    if is_configured():
        return True
    # Also honor an external SDK that already installed a real provider.
    if _ot_trace is not None:
        try:
            provider_type = type(_ot_trace.get_tracer_provider()).__name__
            return provider_type not in {"ProxyTracerProvider", "NoOpTracerProvider"}
        except Exception:  # pragma: no cover - defensive
            return False
    return False


_ENABLED: bool = _resolve_enabled()


def is_enabled() -> bool:
    """True when signal emitters should actually emit (cached)."""
    return _ENABLED


def reload_for_tests() -> bool:
    """Re-evaluate the cached enablement flag from the current environment."""
    global _ENABLED
    _ENABLED = _resolve_enabled()
    return _ENABLED
