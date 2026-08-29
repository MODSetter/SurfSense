"""Tracer/meter/logger provider + OTLP exporter installation."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

from app.observability.core.resource import build_resource

logger = logging.getLogger(__name__)

_TRACER_PROVIDER: Any | None = None
_METER_PROVIDER: Any | None = None
_LOGGER_PROVIDER: Any | None = None


def _otlp_protocol() -> str:
    return os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").strip().lower()


def _trace_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()


def _metric_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    return OTLPMetricExporter(endpoint=endpoint) if endpoint else OTLPMetricExporter()


def _log_exporter():
    if _otlp_protocol() == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    else:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
    return OTLPLogExporter(endpoint=endpoint) if endpoint else OTLPLogExporter()


def install_traces():
    """Install the tracer provider, redacting span processor, and exporter."""
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is not None:
        return _TRACER_PROVIDER

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

    from app.observability.setup.privacy import build_span_exporter

    provider = TracerProvider(
        resource=build_resource(),
        sampler=ParentBased(ALWAYS_ON),
    )
    provider.add_span_processor(
        BatchSpanProcessor(build_span_exporter(_trace_exporter()))
    )

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        logger.warning("tracer provider already set; reusing existing", exc_info=True)
        _TRACER_PROVIDER = trace.get_tracer_provider()
    else:
        _TRACER_PROVIDER = provider
    return _TRACER_PROVIDER


def install_metrics():
    """Install the meter provider, periodic reader, and exporter."""
    global _METER_PROVIDER
    if _METER_PROVIDER is not None:
        return _METER_PROVIDER

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    interval_ms = int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL", "60000"))
    reader = PeriodicExportingMetricReader(
        _metric_exporter(),
        export_interval_millis=interval_ms,
    )
    provider = MeterProvider(metric_readers=[reader], resource=build_resource())

    try:
        metrics.set_meter_provider(provider)
    except Exception:
        logger.warning("meter provider already set; reusing existing", exc_info=True)
        _METER_PROVIDER = metrics.get_meter_provider()
    else:
        _METER_PROVIDER = provider
    return _METER_PROVIDER


def install_logging():
    """Install the logger provider + OTLP log exporter and attach a root handler."""
    global _LOGGER_PROVIDER
    if _LOGGER_PROVIDER is not None:
        return _LOGGER_PROVIDER

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    provider = LoggerProvider(resource=build_resource())
    provider.add_log_record_processor(BatchLogRecordProcessor(_log_exporter()))
    with contextlib.suppress(Exception):
        set_logger_provider(provider)
    _LOGGER_PROVIDER = provider

    root = logging.getLogger()
    if not any(isinstance(handler, LoggingHandler) for handler in root.handlers):
        root.addHandler(LoggingHandler(logger_provider=provider))
    return _LOGGER_PROVIDER


def shutdown(timeout_millis: int = 5000) -> None:
    """Best-effort flush and shutdown for every installed provider."""
    for provider in (_TRACER_PROVIDER, _METER_PROVIDER, _LOGGER_PROVIDER):
        if provider is None:
            continue
        with contextlib.suppress(Exception):
            provider.force_flush(timeout_millis=timeout_millis)
        with contextlib.suppress(Exception):
            provider.shutdown()
