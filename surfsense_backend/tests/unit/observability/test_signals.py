"""Unit tests for the generic signal mechanisms: tracing and metrics."""

from __future__ import annotations

import pytest

from app.observability.core import config
from app.observability.signals import metrics, tracing

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    config.reload_for_tests()
    yield
    config.reload_for_tests()


class TestTracing:
    def test_span_yields_a_usable_noop(self) -> None:
        with tracing.span("any.thing", attributes={"x": 1}) as sp:
            sp.set_attribute("y", 2)
            sp.set_attributes({"a": "b"})
            sp.add_event("evt")
            sp.record_exception(RuntimeError("ignored"))
            sp.set_status("ignored")
        # Reaching here without raising means the no-op is well-formed.

    def test_span_propagates_exceptions(self) -> None:
        with pytest.raises(ValueError), tracing.span("err"):
            raise ValueError("boom")

    def test_add_event_noops_when_disabled(self) -> None:
        tracing.add_event("test.event", {"value": 1})

    def test_add_event_noops_without_current_span(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTrace:
            @staticmethod
            def get_current_span():
                return None

        monkeypatch.setattr(config, "_ENABLED", True)
        monkeypatch.setattr(tracing, "_ot_trace", FakeTrace())
        tracing.add_event("test.event", {"value": 1})

    def test_record_error_noops_when_disabled(self) -> None:
        tracing.record_error(object(), RuntimeError("x"))  # no raise


class TestMetrics:
    def test_perf_elapsed_noops_when_disabled(self) -> None:
        metrics.record_perf_elapsed(7.0, label="[test]")

    def test_record_and_add_skip_instrument_when_disabled(self) -> None:
        class Boom:
            def record(self, *_a, **_k):
                raise AssertionError("must not record when disabled")

            def add(self, *_a, **_k):
                raise AssertionError("must not add when disabled")

        metrics.record(Boom(), 1.0, {"a": "b"})
        metrics.add(Boom(), 1, {"a": "b"})

    def test_attrs_with_error_category(self) -> None:
        assert metrics.attrs_with_error_category({"a": 1}, None) == {"a": 1}
        assert metrics.attrs_with_error_category({"a": 1}, "timeout") == {
            "a": 1,
            "error.category": "timeout",
        }
