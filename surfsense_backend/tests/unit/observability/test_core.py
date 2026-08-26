"""Unit tests for the observability core: enablement, identity, error tokens."""

from __future__ import annotations

import pytest

from app.observability.core import config, errors, resource

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_enablement(monkeypatch: pytest.MonkeyPatch):
    """Force a clean disabled state per test; restore after."""
    for env in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "SURFSENSE_DISABLE_OTEL",
        "OTEL_SDK_DISABLED",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    config.reload_for_tests()
    yield
    config.reload_for_tests()


class TestEnablement:
    def test_disabled_by_default_when_no_endpoint(self) -> None:
        assert config.is_enabled() is False

    def test_enabled_when_endpoint_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        assert config.reload_for_tests() is True

    def test_surfsense_kill_switch_overrides_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
        assert config.reload_for_tests() is False

    def test_spec_kill_switch_overrides_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        assert config.reload_for_tests() is False

    def test_is_disabled_checks_both_kill_switches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_DISABLE_OTEL", raising=False)
        monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
        assert config.is_disabled() is False
        monkeypatch.setenv("OTEL_SDK_DISABLED", "on")
        assert config.is_disabled() is True

    def test_is_configured_honors_shared_or_signal_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert config.is_configured() is False
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4317"
        )
        assert config.is_configured() is True


class TestResource:
    def test_defaults_include_service_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-backend")
        monkeypatch.setenv("SURFSENSE_ENV", "test")
        attrs = dict(resource.build_resource().attributes)
        assert attrs["service.name"] == "custom-backend"
        assert attrs["deployment.environment.name"] == "test"
        assert attrs["deployment.environment"] == "test"
        assert attrs["service.instance.id"]

    def test_deployment_environment_uses_surfsense_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SURFSENSE_ENV", raising=False)
        assert resource.deployment_environment() == "dev"
        monkeypatch.setenv("SURFSENSE_ENV", "production")
        assert resource.deployment_environment() == "production"

    def test_missing_version_key_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An editable/dynamic install can raise KeyError deep in importlib.metadata.
        def _raise_key_error(_name: str) -> str:
            raise KeyError("Version")

        monkeypatch.setattr(resource.metadata, "version", _raise_key_error)
        assert resource.package_version() == "unknown"

    def test_package_not_found_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_not_found(_name: str) -> str:
            raise resource.metadata.PackageNotFoundError("surf-new-backend")

        monkeypatch.setattr(resource.metadata, "version", _raise_not_found)
        assert resource.package_version() == "unknown"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (type("RateLimitError", (Exception,), {})(), "rate_limited"),
        (type("AuthenticationError", (Exception,), {})(), "auth_failed"),
        (type("QuotaInsufficientError", (Exception,), {})(), "quota_exhausted"),
        (TimeoutError(), "timeout"),
        (type("APIConnectionError", (Exception,), {})(), "network_failed"),
        (type("ServiceUnavailableError", (Exception,), {})(), "server_error"),
        (type("LockContentionError", (Exception,), {})(), "lock_contention"),
        (type("UnsupportedFormatError", (Exception,), {})(), "unsupported_format"),
        (type("ProviderError", (Exception,), {})(), "provider_error"),
        (RuntimeError("plain"), "unknown"),
        (None, "unknown"),
    ],
)
def test_categorize_exception(exc: BaseException | None, expected: str) -> None:
    assert errors.categorize_exception(exc) == expected
