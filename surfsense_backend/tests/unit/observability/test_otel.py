"""Tests for the SurfSense OpenTelemetry shim."""

from __future__ import annotations

import pytest

from app.observability import bootstrap, metrics, otel

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_otel_state(monkeypatch: pytest.MonkeyPatch):
    """Force a clean OTel disabled state per test, then restore after."""
    for env in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "SURFSENSE_DISABLE_OTEL",
        "OTEL_SDK_DISABLED",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    otel.reload_for_tests()
    yield
    otel.reload_for_tests()


def test_disabled_by_default_when_no_endpoint() -> None:
    assert otel.is_enabled() is False


def test_enabled_when_endpoint_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    assert otel.reload_for_tests() is True


def test_kill_switch_overrides_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    assert otel.reload_for_tests() is False


def test_spec_kill_switch_overrides_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert otel.reload_for_tests() is False


class TestBootstrapConfig:
    def test_disabled_checks_both_kill_switches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
        assert bootstrap.is_otel_disabled() is False

        monkeypatch.setenv("OTEL_SDK_DISABLED", "on")
        assert bootstrap.is_otel_disabled() is True

    def test_configured_by_shared_or_signal_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        assert bootstrap.is_otel_configured() is False

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4317"
        )
        assert bootstrap.is_otel_configured() is True

    def test_init_otel_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"traces": False}

        def fake_init_traces(app=None):
            del app
            called["traces"] = True

        monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setattr(bootstrap, "init_traces", fake_init_traces)

        bootstrap.init_otel()
        assert called["traces"] is False

    def test_init_otel_dispatches_enabled_signals(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: list[str] = []

        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setattr(
            bootstrap, "init_traces", lambda app=None: called.append("traces")
        )
        monkeypatch.setattr(bootstrap, "init_metrics", lambda: called.append("metrics"))
        monkeypatch.setattr(bootstrap, "init_logs", lambda: called.append("logs"))

        bootstrap.init_otel()
        assert called == ["traces", "metrics", "logs"]

    def test_resource_defaults_include_service_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-backend")
        monkeypatch.setenv("SURFSENSE_ENV", "test")

        resource = bootstrap._build_resource()
        attrs = dict(resource.attributes)
        assert attrs["service.name"] == "custom-backend"
        assert attrs["deployment.environment.name"] == "test"
        assert attrs["deployment.environment"] == "test"
        assert attrs["service.instance.id"]

    def test_deployment_environment_uses_surfsense_env_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_ENV", raising=False)

        assert bootstrap._deployment_environment() == "dev"

        monkeypatch.setenv("SURFSENSE_ENV", "production")

        assert bootstrap._deployment_environment() == "production"

    def test_shutdown_is_safe_without_providers(self) -> None:
        bootstrap.shutdown_otel()

    def test_init_logs_enables_log_correlation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []

        class FakeLoggingInstrumentor:
            def instrument(self, **kwargs: object) -> None:
                calls.append(kwargs)

        def fake_safe_instrument(name: str, callback):
            assert name == "logging"
            monkeypatch.setattr(
                "opentelemetry.instrumentation.logging.LoggingInstrumentor",
                FakeLoggingInstrumentor,
            )
            callback()
            return True

        monkeypatch.setattr(bootstrap, "_LOGS_INITIALIZED", False)
        monkeypatch.setattr(bootstrap, "_safe_instrument", fake_safe_instrument)

        bootstrap.init_logs()

        assert calls == [{"set_logging_format": True}]


class TestMetricHelpers:
    def test_all_metric_helpers_noop_safely_when_disabled(self) -> None:
        metrics.record_model_call_duration(12.5, model="gpt-4o", provider="openai")
        metrics.record_model_token_usage(
            input_tokens=10,
            output_tokens=5,
            model="gpt-4o",
            provider="openai",
        )
        metrics.record_tool_call_duration(3.0, tool_name="scrape_webpage")
        metrics.record_tool_call_error(tool_name="scrape_webpage")
        metrics.record_kb_search_duration(
            4.0,
            workspace_id=1,
            surface="documents",
        )
        metrics.record_compaction_run(reason="auto")
        metrics.record_permission_ask(permission="write_file")
        metrics.record_interrupt(interrupt_type="permission_ask")
        metrics.record_indexing_document_duration(1.2, document_type="FILE")
        metrics.record_indexing_document_outcome(document_type="FILE", status="success")
        metrics.record_connector_sync_duration(
            2.3,
            connector_type="index_notion_pages",
        )
        metrics.record_connector_sync_outcome(
            connector_type="index_notion_pages",
            status="success",
        )
        metrics.record_auth_failure(reason="UNAUTHORIZED")
        metrics.record_rate_limit_rejection(scope="login")
        metrics.record_perf_elapsed(7.0, label="[test]")

    def test_runtime_observables_register_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeMeter:
            def __init__(self) -> None:
                self.names: list[str] = []

            def create_observable_gauge(self, name: str, **kwargs) -> None:
                del kwargs
                self.names.append(name)

        fake_meter = FakeMeter()
        monkeypatch.setattr(metrics, "_OBSERVABLES_REGISTERED", False)
        monkeypatch.setattr(metrics, "_is_enabled", lambda: True)
        monkeypatch.setattr(metrics, "_get_meter", lambda: fake_meter)

        metrics.register_runtime_observables()
        metrics.register_runtime_observables()

        assert len(fake_meter.names) == 6
        assert fake_meter.names.count("python.asyncio.tasks") == 1
        monkeypatch.setattr(metrics, "_OBSERVABLES_REGISTERED", False)


def test_log_record_factory_provides_zero_otel_fields() -> None:
    import logging

    import main  # noqa: F401

    record = logging.getLogRecordFactory()(
        "test",
        logging.INFO,
        __file__,
        1,
        "hello",
        (),
        None,
    )
    assert record.otelTraceID == "0"
    assert record.otelSpanID == "0"


class TestNoopSpansWhenDisabled:
    def test_generic_span_yields_noop(self) -> None:
        with otel.span("any.thing", attributes={"x": 1}) as sp:
            sp.set_attribute("y", 2)
            sp.set_attributes({"a": "b"})
            sp.add_event("evt")
            sp.record_exception(RuntimeError("ignored"))
            sp.set_status("ignored")
        # Reaching here without raising means the no-op is well-formed

    def test_exception_propagates_through_span(self) -> None:
        with pytest.raises(ValueError), otel.span("err"):
            raise ValueError("boom")

    def test_each_helper_is_a_no_op_when_disabled(self) -> None:
        helpers = [
            otel.tool_call_span("write_file", input_size=42),
            otel.model_call_span(model_id="openai:gpt-4o", provider="openai"),
            otel.kb_search_span(workspace_id=1, query_chars=99),
            otel.kb_persist_span(document_type="NOTE", document_id=7),
            otel.compaction_span(reason="overflow", messages_in=120),
            otel.interrupt_span(interrupt_type="permission_ask"),
            otel.permission_asked_span(permission="edit", pattern="/x/**"),
        ]
        for cm in helpers:
            with cm as sp:
                assert sp is not None
                sp.set_attribute("ok", True)


class TestEnabledIntegration:
    """When OTel is wired but no SDK exporter is bound, the API still works."""

    def test_span_attaches_attributes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Use the API tracer (no-op-ish but real Span objects).
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        assert otel.reload_for_tests() is True

        # Should not raise even when set_attributes/record_exception fall through
        # to an SDK that isn't actually installed.
        with otel.tool_call_span("scrape_webpage", input_size=10) as sp:
            sp.set_attribute("tool.output.size", 200)
            sp.set_attribute("tool.truncated", False)
        with otel.model_call_span(model_id="m", provider="p") as sp:
            sp.set_attribute("retry.count", 3)


class TestPackageVersionResilience:
    """A version-tag lookup must never crash the request path (e.g. subagents).

    An editable/dynamic install can have distribution metadata with no
    ``Version`` field, which raises ``KeyError`` deep inside importlib.metadata.
    ``_package_version`` must swallow that and every other lookup failure.
    """

    def test_missing_version_key_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_key_error(_name: str) -> str:
            raise KeyError("Version")

        monkeypatch.setattr(metrics.metadata, "version", _raise_key_error)
        assert metrics._package_version() == "unknown"

    def test_package_not_found_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_not_found(_name: str) -> str:
            raise metrics.metadata.PackageNotFoundError("surf-new-backend")

        monkeypatch.setattr(metrics.metadata, "version", _raise_not_found)
        assert metrics._package_version() == "unknown"
