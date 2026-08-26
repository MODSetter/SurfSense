"""Unit tests for process wiring: lifecycle dispatch and log correlation."""

from __future__ import annotations

import logging

import pytest

from app.observability.core import config
from app.observability.setup import instrumentation, lifecycle, providers

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_enablement(monkeypatch: pytest.MonkeyPatch):
    for env in ("OTEL_EXPORTER_OTLP_ENDPOINT", "SURFSENSE_DISABLE_OTEL", "OTEL_SDK_DISABLED"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    config.reload_for_tests()
    yield
    config.reload_for_tests()


class TestLifecycle:
    def test_init_otel_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"traces": False}
        monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setattr(
            providers, "install_traces", lambda: called.__setitem__("traces", True)
        )
        lifecycle.init_otel()
        assert called["traces"] is False

    def test_init_otel_dispatches_signals_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: list[str] = []
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setattr(providers, "install_traces", lambda: called.append("traces"))
        monkeypatch.setattr(providers, "install_metrics", lambda: called.append("metrics"))
        monkeypatch.setattr(providers, "install_logging", lambda: called.append("logs"))
        monkeypatch.setattr(instrumentation, "instrument_logging", lambda: None)
        monkeypatch.setattr(instrumentation, "instrument_libraries", lambda app=None: None)
        monkeypatch.setattr(
            "app.observability.domains.runtime.register_runtime_observables",
            lambda: called.append("runtime"),
        )
        lifecycle.init_otel()
        assert called == ["traces", "metrics", "runtime", "logs"]

    def test_shutdown_is_safe_without_providers(self) -> None:
        lifecycle.shutdown_otel()


class TestLogCorrelation:
    def test_instrument_logging_sets_correlation_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []

        class FakeLoggingInstrumentor:
            def instrument(self, **kwargs: object) -> None:
                calls.append(kwargs)

        monkeypatch.setattr(instrumentation, "_LOGGING", False)
        monkeypatch.setattr(
            "opentelemetry.instrumentation.logging.LoggingInstrumentor",
            FakeLoggingInstrumentor,
        )
        instrumentation.instrument_logging()
        assert calls == [{"set_logging_format": True}]

    def test_log_record_factory_provides_zero_otel_fields(self) -> None:
        # main.py installs a factory so stdlib records carry otel fields even
        # before OTel binds real IDs (avoids KeyError in the log format).
        import main  # noqa: F401

        record = logging.getLogRecordFactory()(
            "test", logging.INFO, __file__, 1, "hello", (), None
        )
        assert record.otelTraceID == "0"
        assert record.otelSpanID == "0"
