"""Unit tests for the PostHog analytics wrapper.

Covers the two properties the rest of the codebase relies on:
1. Opt-in no-op: with no client configured, every entry point is silent and
   never raises (analytics must never break a request).
2. Correct stamping when a client IS present: ``source="backend"`` and
   ``disable_geoip=True`` on every capture, plus ``auth_method`` / ``client``
   derived from the ``AuthContext`` principal by ``capture_for``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.observability import analytics

pytestmark = pytest.mark.unit


class _FakeClient:
    """Records capture()/group_identify() calls instead of hitting the network."""

    def __init__(self) -> None:
        self.captures: list[dict] = []
        self.groups: list[dict] = []

    def capture(self, event, *, distinct_id, properties, groups, disable_geoip):
        self.captures.append(
            {
                "event": event,
                "distinct_id": distinct_id,
                "properties": properties,
                "groups": groups,
                "disable_geoip": disable_geoip,
            }
        )

    def group_identify(self, *, group_type, group_key, properties):
        self.groups.append(
            {"group_type": group_type, "group_key": group_key, "properties": properties}
        )


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Isolate the module-level lazy-client singleton between tests."""
    orig_client = analytics._client
    orig_attempted = analytics._init_attempted
    yield
    analytics._client = orig_client
    analytics._init_attempted = orig_attempted


def _use_fake_client() -> _FakeClient:
    """Inject a fake client, bypassing lazy init (no posthog import, no key)."""
    fake = _FakeClient()
    analytics._client = fake
    analytics._init_attempted = True
    return fake


def _disable_client() -> None:
    analytics._client = None
    analytics._init_attempted = True


# ---- No-op behaviour when disabled -------------------------------------------------


def test_capture_is_noop_without_client():
    _disable_client()
    assert analytics.is_enabled() is False
    # Must not raise even though there is no client.
    analytics.capture("some_event", distinct_id="u1", properties={"a": 1})


def test_capture_for_is_noop_without_client():
    _disable_client()
    auth = SimpleNamespace(method="session", source=None, user=SimpleNamespace(id="u1"))
    analytics.capture_for(auth, "some_event", {"a": 1})  # no raise


def test_shutdown_is_noop_without_client():
    _disable_client()
    analytics.shutdown()  # no raise


# ---- Stamping when a client is present ---------------------------------------------


def test_capture_stamps_source_and_disables_geoip():
    fake = _use_fake_client()
    analytics.capture(
        "chat_turn_completed",
        distinct_id="user-123",
        properties={"workspace_id": 7},
        groups={"workspace": "7"},
    )

    assert len(fake.captures) == 1
    call = fake.captures[0]
    assert call["event"] == "chat_turn_completed"
    assert call["distinct_id"] == "user-123"
    # source is always stamped so backend vs frontend events are separable.
    assert call["properties"]["source"] == "backend"
    assert call["properties"]["workspace_id"] == 7
    assert call["groups"] == {"workspace": "7"}
    # Without this the server IP would overwrite each person's real location.
    assert call["disable_geoip"] is True


def test_capture_never_raises_when_client_errors():
    class _Boom(_FakeClient):
        def capture(self, *a, **k):
            raise RuntimeError("network down")

    boom = _Boom()
    analytics._client = boom
    analytics._init_attempted = True
    # Swallowed like the frontend safeCapture — analytics never breaks a request.
    analytics.capture("evt", distinct_id="u1")


@pytest.mark.parametrize(
    ("method", "source", "expected_client"),
    [
        ("session", None, "web"),
        ("pat", None, "pat"),
        ("system", "gateway", "gateway"),
        ("system", None, "system"),
    ],
)
def test_capture_for_stamps_auth_method_and_client(method, source, expected_client):
    fake = _use_fake_client()
    auth = SimpleNamespace(
        method=method, source=source, user=SimpleNamespace(id="user-abc")
    )

    analytics.capture_for(auth, "workspace_created", {"workspace_id": 1})

    assert len(fake.captures) == 1
    props = fake.captures[0]["properties"]
    assert fake.captures[0]["distinct_id"] == "user-abc"
    assert props["auth_method"] == method
    assert props["client"] == expected_client
    assert props["source"] == "backend"  # capture_for delegates to capture
    assert props["workspace_id"] == 1
