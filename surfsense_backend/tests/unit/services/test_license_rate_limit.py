"""The two token buckets guarding the unauthenticated POST license routes.

One bucket on the caller's IP, one on the folded email. Either being empty is
a 429, so a single address cannot be flooded from many IPs and a single IP
cannot walk many addresses.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

pytestmark = pytest.mark.unit


class _Request:
    def __init__(self, ip: str = "203.0.113.9", headers: dict | None = None):
        self.client = type("C", (), {"host": ip})()
        self.headers = Headers(headers or {})


@pytest.fixture
def buckets(monkeypatch):
    """Record every bucket consumed, and let tests choose which are empty."""
    from app.services import license_rate_limit

    calls: list[tuple[str, int]] = []
    empty: set[str] = set()

    async def fake_acquire(scope, *, capacity, refill_per_sec, consume=1.0):
        calls.append((scope, capacity))
        return 1000 if any(marker in scope for marker in empty) else 0

    monkeypatch.setattr(license_rate_limit, "acquire_token", fake_acquire)
    return calls, empty


async def test_both_buckets_are_consumed(buckets, monkeypatch):
    from app.config import config
    from app.services.license_rate_limit import enforce_license_rate_limit

    calls, _ = buckets
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 10)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 5)

    await enforce_license_rate_limit(
        _Request(), route="resend", email="Buyer+tag@Example.com"
    )

    scopes = [scope for scope, _ in calls]
    assert "license:resend:ip:203.0.113.9" in scopes
    # Folded, so plus-tagging cannot buy extra attempts.
    assert "license:resend:email:buyer@example.com" in scopes


async def test_an_empty_ip_bucket_is_a_429(buckets):
    from app.services.license_rate_limit import enforce_license_rate_limit

    _, empty = buckets
    empty.add(":ip:")

    with pytest.raises(HTTPException) as exc:
        await enforce_license_rate_limit(
            _Request(), route="trial", email="a@example.com"
        )

    assert exc.value.status_code == 429


async def test_an_empty_email_bucket_is_a_429(buckets):
    """One address cannot be flooded by rotating IPs."""
    from app.services.license_rate_limit import enforce_license_rate_limit

    _, empty = buckets
    empty.add(":email:")

    with pytest.raises(HTTPException) as exc:
        await enforce_license_rate_limit(
            _Request(ip="198.51.100.4"), route="resend", email="a@example.com"
        )

    assert exc.value.status_code == 429


async def test_each_route_has_its_own_budget(buckets, monkeypatch):
    from app.config import config
    from app.services.license_rate_limit import enforce_license_rate_limit

    calls, _ = buckets
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 5)
    monkeypatch.setattr(config, "LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", 3)

    await enforce_license_rate_limit(_Request(), route="resend", email="a@b.test")
    await enforce_license_rate_limit(_Request(), route="trial", email="a@b.test")

    capacities = {scope: capacity for scope, capacity in calls if ":email:" in scope}
    assert capacities["license:resend:email:a@b.test"] == 5
    assert capacities["license:trial:email:a@b.test"] == 3


async def test_a_zero_limit_disables_that_bucket(buckets, monkeypatch):
    """Zero means off, not "reject everything" -- self-hosters turn these off."""
    from app.config import config
    from app.services.license_rate_limit import enforce_license_rate_limit

    calls, empty = buckets
    empty.add(":ip:")
    monkeypatch.setattr(config, "LICENSE_RATE_LIMIT_IP_PER_HOUR", 0)
    monkeypatch.setattr(config, "LICENSE_RESEND_RATE_LIMIT_PER_HOUR", 5)

    await enforce_license_rate_limit(_Request(), route="resend", email="a@b.test")

    assert all(":ip:" not in scope for scope, _ in calls)


async def test_the_proxy_header_is_used_as_the_client_ip(buckets):
    """The deployment sits behind Caddy and Cloudflare; the socket peer is theirs."""
    from app.services.license_rate_limit import enforce_license_rate_limit

    calls, _ = buckets
    await enforce_license_rate_limit(
        _Request(headers={"cf-connecting-ip": "192.0.2.7"}),
        route="resend",
        email="a@b.test",
    )

    assert any("ip:192.0.2.7" in scope for scope, _ in calls)
