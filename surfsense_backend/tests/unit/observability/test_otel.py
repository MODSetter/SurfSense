"""Tests for the SurfSense OpenTelemetry shim."""

from __future__ import annotations

import pytest

from app.observability import otel

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_otel_state(monkeypatch: pytest.MonkeyPatch):
    """Force a clean OTel disabled state per test, then restore after."""
    for env in ("OTEL_EXPORTER_OTLP_ENDPOINT", "SURFSENSE_DISABLE_OTEL"):
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
            otel.kb_search_span(search_space_id=1, query_chars=99),
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
