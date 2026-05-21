"""Programmatic OpenTelemetry bootstrap for SurfSense backend processes."""

from __future__ import annotations

import contextlib
import logging
import os
import socket
from importlib import metadata
from typing import Any

from app.observability import otel

logger = logging.getLogger(__name__)

_BOOL_TRUE = {"1", "true", "yes", "on"}

_TRACES_INITIALIZED = False
_METRICS_INITIALIZED = False
_LOGS_INITIALIZED = False
_FASTAPI_INSTRUMENTED = False
_SQLALCHEMY_INSTRUMENTED = False
_PSYCOPG_INSTRUMENTED = False
_REDIS_INSTRUMENTED = False
_HTTPX_INSTRUMENTED = False
_CELERY_INSTRUMENTED = False

_TRACER_PROVIDER: Any | None = None
_METER_PROVIDER: Any | None = None


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _BOOL_TRUE


def is_otel_disabled() -> bool:
    """Return true when either SurfSense or OTel's spec kill switch is set."""
    return _env_truthy("SURFSENSE_DISABLE_OTEL") or _env_truthy("OTEL_SDK_DISABLED")


def is_otel_configured() -> bool:
    """Return true when this process should export OTel signals."""
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    )


def _package_version() -> str:
    with contextlib.suppress(metadata.PackageNotFoundError):
        return metadata.version("surf-new-backend")
    return "unknown"


def _deployment_environment() -> str:
    return (
        os.environ.get("SURFSENSE_ENV")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or "dev"
    )


def _build_resource():
    from opentelemetry.sdk.resources import Resource

    return Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "surfsense-backend"),
            "service.version": _package_version(),
            "service.instance.id": socket.gethostname(),
            "deployment.environment": _deployment_environment(),
        }
    )


def _otlp_protocol() -> str:
    return os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").strip().lower()


def _trace_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()


def _metric_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
        return (
            OTLPMetricExporter(endpoint=endpoint) if endpoint else OTLPMetricExporter()
        )

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    return OTLPMetricExporter(endpoint=endpoint) if endpoint else OTLPMetricExporter()


def _safe_instrument(name: str, instrument: Any) -> bool:
    try:
        instrument()
    except Exception:
        logger.warning("OpenTelemetry %s instrumentation failed", name, exc_info=True)
        return False
    return True


def _instrument_fastapi(app: Any | None) -> None:
    global _FASTAPI_INSTRUMENTED
    if app is None or _FASTAPI_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/ready,/metrics",
        )

    if _safe_instrument("FastAPI", _run):
        _FASTAPI_INSTRUMENTED = True


def instrument_sqlalchemy_engine(engine: Any) -> None:
    """Instrument a SQLAlchemy engine once per process."""
    global _SQLALCHEMY_INSTRUMENTED
    if _SQLALCHEMY_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(
            engine=getattr(engine, "sync_engine", engine),
            enable_commenter=True,
        )

    if _safe_instrument("SQLAlchemy", _run):
        _SQLALCHEMY_INSTRUMENTED = True


def _instrument_sqlalchemy() -> None:
    if _SQLALCHEMY_INSTRUMENTED:
        return
    with contextlib.suppress(Exception):
        from app.db import engine

        instrument_sqlalchemy_engine(engine)


def _instrument_psycopg() -> None:
    global _PSYCOPG_INSTRUMENTED
    if _PSYCOPG_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

        PsycopgInstrumentor().instrument()

    if _safe_instrument("psycopg", _run):
        _PSYCOPG_INSTRUMENTED = True


def _instrument_redis() -> None:
    global _REDIS_INSTRUMENTED
    if _REDIS_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()

    if _safe_instrument("Redis", _run):
        _REDIS_INSTRUMENTED = True


def _instrument_httpx() -> None:
    global _HTTPX_INSTRUMENTED
    if _HTTPX_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

    if _safe_instrument("HTTPX", _run):
        _HTTPX_INSTRUMENTED = True


def instrument_celery() -> None:
    """Instrument Celery producer/consumer hooks once per process."""
    global _CELERY_INSTRUMENTED
    if _CELERY_INSTRUMENTED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()

    if _safe_instrument("Celery", _run):
        _CELERY_INSTRUMENTED = True


def _instrument_libraries(app: Any | None) -> None:
    _instrument_fastapi(app)
    _instrument_sqlalchemy()
    _instrument_psycopg()
    _instrument_redis()
    _instrument_httpx()
    instrument_celery()


def init_traces(app: Any | None = None) -> None:
    """Install the tracer provider, span processor, exporter, and instrumentors."""
    global _TRACER_PROVIDER, _TRACES_INITIALIZED
    if _TRACES_INITIALIZED:
        _instrument_fastapi(app)
        return

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

    provider = TracerProvider(
        resource=_build_resource(),
        sampler=ParentBased(ALWAYS_ON),
    )
    provider.add_span_processor(BatchSpanProcessor(_trace_exporter()))

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        logger.warning(
            "OpenTelemetry tracer provider was already set; reusing existing provider",
            exc_info=True,
        )
        _TRACER_PROVIDER = trace.get_tracer_provider()
    else:
        _TRACER_PROVIDER = provider

    _TRACES_INITIALIZED = True
    otel.reload_for_tests()
    _instrument_libraries(app)


def init_metrics() -> None:
    """Install the meter provider, metric reader, exporter, and custom gauges."""
    global _METER_PROVIDER, _METRICS_INITIALIZED
    if _METRICS_INITIALIZED:
        return

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    interval_ms = int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL", "60000"))
    reader = PeriodicExportingMetricReader(
        _metric_exporter(),
        export_interval_millis=interval_ms,
    )
    provider = MeterProvider(metric_readers=[reader], resource=_build_resource())

    try:
        metrics.set_meter_provider(provider)
    except Exception:
        logger.warning(
            "OpenTelemetry meter provider was already set; reusing existing provider",
            exc_info=True,
        )
        _METER_PROVIDER = metrics.get_meter_provider()
    else:
        _METER_PROVIDER = provider

    _METRICS_INITIALIZED = True
    from app.observability.metrics import register_runtime_observables

    register_runtime_observables()


def init_logs() -> None:
    """Enable trace/span correlation fields on stdlib LogRecords."""
    global _LOGS_INITIALIZED
    if _LOGS_INITIALIZED:
        return

    def _run() -> None:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument()

    if _safe_instrument("logging", _run):
        _LOGS_INITIALIZED = True


def init_otel(
    app: Any | None = None,
    *,
    traces: bool = True,
    metrics: bool = True,
    logs: bool = True,
) -> None:
    """Initialize OpenTelemetry for a FastAPI or Celery process."""
    if is_otel_disabled() or not is_otel_configured():
        otel.reload_for_tests()
        return

    if traces:
        init_traces(app)
    if metrics:
        init_metrics()
    if logs:
        init_logs()


def shutdown_otel(timeout_millis: int = 5000) -> None:
    """Best-effort flush and shutdown for installed providers."""
    for provider in (_TRACER_PROVIDER, _METER_PROVIDER):
        if provider is None:
            continue
        with contextlib.suppress(Exception):
            provider.force_flush(timeout_millis=timeout_millis)
        with contextlib.suppress(Exception):
            provider.shutdown()


__all__ = [
    "_BOOL_TRUE",
    "_build_resource",
    "init_logs",
    "init_metrics",
    "init_otel",
    "init_traces",
    "instrument_celery",
    "instrument_sqlalchemy_engine",
    "is_otel_configured",
    "is_otel_disabled",
    "shutdown_otel",
]
