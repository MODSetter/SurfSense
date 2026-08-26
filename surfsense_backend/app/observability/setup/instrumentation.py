"""Library auto-instrumentation and log-record correlation."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from app.observability.setup.privacy import sanitize_http_span_url

logger = logging.getLogger(__name__)

_FASTAPI = False
_SQLALCHEMY = False
_PSYCOPG = False
_REDIS = False
_HTTPX = False
_CELERY = False
_LOGGING = False


def _safe(name: str, run: Any) -> bool:
    try:
        run()
    except Exception:
        logger.warning("OpenTelemetry %s instrumentation failed", name, exc_info=True)
        return False
    return True


def instrument_fastapi(app: Any | None) -> None:
    global _FASTAPI
    if app is None or _FASTAPI:
        return

    def run() -> None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/ready,/metrics")

    if _safe("FastAPI", run):
        _FASTAPI = True


def instrument_sqlalchemy_engine(engine: Any) -> None:
    """Instrument a SQLAlchemy engine once per process."""
    global _SQLALCHEMY
    if _SQLALCHEMY:
        return

    def run() -> None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(
            engine=getattr(engine, "sync_engine", engine),
            enable_commenter=True,
        )

    if _safe("SQLAlchemy", run):
        _SQLALCHEMY = True


def _instrument_sqlalchemy() -> None:
    if _SQLALCHEMY:
        return
    with contextlib.suppress(Exception):
        from app.db import engine

        instrument_sqlalchemy_engine(engine)


def instrument_psycopg() -> None:
    global _PSYCOPG
    if _PSYCOPG:
        return

    def run() -> None:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

        PsycopgInstrumentor().instrument()

    if _safe("psycopg", run):
        _PSYCOPG = True


def instrument_redis() -> None:
    global _REDIS
    if _REDIS:
        return

    def run() -> None:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()

    if _safe("Redis", run):
        _REDIS = True


def instrument_httpx() -> None:
    global _HTTPX
    if _HTTPX:
        return

    def run() -> None:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument(
            request_hook=lambda span, request: sanitize_http_span_url(span, request),
            response_hook=lambda span, request, _response: sanitize_http_span_url(
                span, request
            ),
        )

    if _safe("HTTPX", run):
        _HTTPX = True


def instrument_celery() -> None:
    """Instrument Celery producer/consumer hooks once per process."""
    global _CELERY
    if _CELERY:
        return

    def run() -> None:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()

    if _safe("Celery", run):
        _CELERY = True


def instrument_logging() -> None:
    """Stamp otelTraceID/otelSpanID onto stdlib LogRecords for trace correlation."""
    global _LOGGING
    if _LOGGING:
        return

    def run() -> None:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)

    if _safe("logging", run):
        _LOGGING = True


def instrument_libraries(app: Any | None) -> None:
    """Instrument every supported library once per process."""
    instrument_fastapi(app)
    _instrument_sqlalchemy()
    instrument_psycopg()
    instrument_redis()
    instrument_httpx()
    instrument_celery()
