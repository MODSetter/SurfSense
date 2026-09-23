"""Contract 4: the sunset flag on ``GET /health``.

Spec: ``docs/contracts/04-sunset-flag.md``. Legacy desktop
v0.0.40 asks this endpoint one question at startup and, when the answer is yes,
loads the live ``/sunset`` page instead of its bundled frontend.

The flag is thrown once, at T-0, and every failure mode here is silent: the
client fails open by design, so a wrong value, a wrong type, or a newly
rate-limited endpoint all look exactly like "not sunset yet".
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.app import app, health_check, limiter

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _health(client: TestClient) -> dict:
    response = client.get("/health")
    assert response.status_code == 200
    return response.json()


def test_the_flag_is_off_when_the_variable_is_unset(client, monkeypatch):
    """Self-hosters never set it, and they must never see a sunset."""
    monkeypatch.delenv("SUNSET_MODE", raising=False)

    assert _health(client)["sunset"] is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "on"])
def test_every_documented_spelling_turns_the_flag_on(client, monkeypatch, value):
    """Contract 4 writes ``SUNSET_MODE=1``; this codebase writes ``TRUE``.

    Both have to work. The cost of a spelling that silently reads as false is
    a sunset day where nothing happens and nothing says why.
    """
    monkeypatch.setenv("DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("SUNSET_MODE", value)

    assert _health(client)["sunset"] is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "  "])
def test_anything_else_leaves_the_flag_off(client, monkeypatch, value):
    monkeypatch.setenv("DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("SUNSET_MODE", value)

    assert _health(client)["sunset"] is False


def test_self_hosted_stays_off_even_if_sunset_mode_is_set(client, monkeypatch):
    """A stray ``SUNSET_MODE=1`` in a self-hosted ``.env`` must be a no-op."""
    monkeypatch.delenv("DEPLOYMENT_MODE", raising=False)
    monkeypatch.setenv("SUNSET_MODE", "1")

    assert _health(client)["sunset"] is False


def test_the_flag_is_read_per_request(client, monkeypatch):
    """No restart beyond the flag change, so it cannot be cached at import."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "cloud")
    monkeypatch.delenv("SUNSET_MODE", raising=False)
    assert _health(client)["sunset"] is False

    monkeypatch.setenv("SUNSET_MODE", "1")
    assert _health(client)["sunset"] is True


def test_sunset_is_a_json_boolean_not_a_string(client, monkeypatch):
    """The consumer tests ``sunset === true``, so a string never matches.

    ``is True`` rather than ``== True`` on purpose: ``1 == True`` in Python, so
    equality would pass on the raw environment value this once returned.
    """
    monkeypatch.setenv("DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("SUNSET_MODE", "1")

    assert isinstance(_health(client)["sunset"], bool)


def test_the_default_sunset_url_is_served_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("SUNSET_URL", raising=False)

    assert _health(client)["sunset_url"] == "https://surfsense.com/sunset"


def test_the_sunset_url_can_be_overridden(client, monkeypatch):
    monkeypatch.setenv("SUNSET_URL", "https://example.test/gone")

    assert _health(client)["sunset_url"] == "https://example.test/gone"


def test_health_needs_no_credentials(client):
    """The client asks before anyone has signed in, and carries no token."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_stays_exempt_from_rate_limiting():
    """A limited /health would 429 some clients, which they read as "no sunset".

    Asserted against the limiter's registry rather than by exhausting a bucket:
    the registry is exact and instant, where hammering is slow and depends on
    whatever the configured limit happens to be.
    """
    assert f"{health_check.__module__}.{health_check.__name__}" in (
        limiter._exempt_routes
    )
