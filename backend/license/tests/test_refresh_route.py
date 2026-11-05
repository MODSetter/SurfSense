"""`POST /license/refresh`: the app trades the key it holds for the license's current file.

Keygen is faked at its transport; the token bucket is the real one, on its
per-process fallback.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import FastAPI

from license import keygen, refresh_route
from license import token_bucket as ratelimit
from license.portal import license_portal
from license.settings import config
from license.tests.test_license_routes import FakeKeygen

pytestmark = pytest.mark.unit


@pytest.fixture
def keygen_store(monkeypatch: pytest.MonkeyPatch) -> FakeKeygen:
    fake = FakeKeygen()

    @asynccontextmanager
    async def http(client=None):
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake.handle)
        ) as session:
            yield session

    def redis_down() -> None:
        raise OSError("no Redis in unit tests")

    monkeypatch.setattr(keygen, "_http", http)
    monkeypatch.setattr(ratelimit, "_redis", redis_down)
    monkeypatch.setattr(ratelimit, "_memory_buckets", {})
    for name, value in {
        "KEYGEN_ACCOUNT_ID": "acct",
        "KEYGEN_API_TOKEN": "product-token",
        "KEYGEN_API_URL": "",
        "KEYGEN_HOST": "",
        "LICENSE_REFRESH_RATE_LIMIT_PER_HOUR": 100,
        "LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR": 100,
    }.items():
        monkeypatch.setattr(config, name, value)
    return fake


async def refresh(key: str, ip: str = "203.0.113.1") -> httpx2.Response:
    app = FastAPI()
    app.include_router(refresh_route.router)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        return await client.post(
            "/license/refresh", json={"key": key}, headers={"X-Real-IP": ip}
        )


def renewed_on_this_key(store: FakeKeygen) -> None:
    store.add(
        "lic-firm",
        expiry=(datetime.now(UTC) + timedelta(days=400)).isoformat(),
        plan="business",
        email="partner@acme.example",
    )


async def test_a_known_key_gets_a_fresh_file(keygen_store: FakeKeygen) -> None:
    renewed_on_this_key(keygen_store)

    reply = await refresh("KEY-lic-firm")

    assert reply.status_code == 200
    assert reply.text == "CERT-lic-firm"
    assert (
        reply.headers["content-disposition"] == 'attachment; filename="surfsense.lic"'
    )
    # The file carries the key; no proxy may keep a copy.
    assert reply.headers["cache-control"] == "no-store"


async def test_the_key_is_validated_before_any_check_out(
    keygen_store: FakeKeygen,
) -> None:
    renewed_on_this_key(keygen_store)

    await refresh("KEY-lic-firm")

    paths = [request.url.path for request in keygen_store.requests]
    assert paths[0].endswith("/licenses/actions/validate-key")
    assert paths[1].endswith("/licenses/lic-firm/actions/check-out")


async def test_a_suspended_license_gets_no_file(keygen_store: FakeKeygen) -> None:
    """Refunded or disputed: Keygen would check a file out regardless, so the server refuses."""
    keygen_store.add("lic-refunded", status="SUSPENDED", plan="business")

    reply = await refresh("KEY-lic-refunded")

    assert reply.status_code == 403
    assert "SUSPENDED" in reply.json()["detail"]
    assert not any(
        request.url.path.endswith("/check-out") for request in keygen_store.requests
    )


async def test_a_lapsed_license_still_gets_its_file(keygen_store: FakeKeygen) -> None:
    """The file says expired, as the app already shows; refusing it would say nothing more."""
    keygen_store.add(
        "lic-lapsed",
        expiry=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
        plan="business",
    )

    reply = await refresh("KEY-lic-lapsed")

    assert reply.status_code == 200


async def test_an_unknown_key_is_404(keygen_store: FakeKeygen) -> None:
    reply = await refresh("KEY-nobody")

    assert reply.status_code == 404


async def test_a_key_is_never_put_in_a_bucket_name(keygen_store: FakeKeygen) -> None:
    """It is a bearer credential; Redis keys and their logs must not hold it."""
    renewed_on_this_key(keygen_store)

    await refresh("KEY-lic-firm")

    assert ratelimit._memory_buckets
    assert not any("KEY-lic-firm" in name for name in ratelimit._memory_buckets)


async def test_the_key_bucket_bites_across_callers(
    keygen_store: FakeKeygen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A firm shares one key; a leaked one is still bounded."""
    renewed_on_this_key(keygen_store)
    monkeypatch.setattr(config, "LICENSE_REFRESH_RATE_LIMIT_PER_HOUR", 2)

    codes = [
        (await refresh("KEY-lic-firm", ip=f"203.0.113.{n}")).status_code
        for n in range(3)
    ]

    assert codes == [200, 200, 429]


async def test_the_ip_bucket_bites_across_keys(
    keygen_store: FakeKeygen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One caller trying keys is still one caller."""
    monkeypatch.setattr(config, "LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR", 2)

    codes = [(await refresh(f"KEY-guess-{n}")).status_code for n in range(3)]

    assert codes == [404, 404, 429]


async def test_keygen_down_is_503(keygen_store: FakeKeygen) -> None:
    keygen_store.down = True

    reply = await refresh("KEY-lic-firm")

    assert reply.status_code == 503


async def test_the_portal_serves_the_refresh(keygen_store: FakeKeygen) -> None:
    portal = license_portal()
    assert portal is not None
    app = FastAPI()
    app.include_router(portal)

    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://portal"
    ) as client:
        reply = await client.post("/api/v1/license/refresh", json={"key": "KEY-x"})

    assert reply.json() == {"detail": "No license has that key."}
