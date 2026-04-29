"""SurfSense observability surface.

The single user-visible API right now is :mod:`otel`, which exposes a
small wrapper around the optional ``opentelemetry`` instrumentation. The
wrapper is a no-op when OTEL is not configured, so importing it from
performance-critical paths is safe.
"""
