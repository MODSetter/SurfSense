"""Stand-ins for the licence slice: PostHog recorded instead of sent, the tests' pack key
trusted, the job pack route over a faked Keygen, and GitHub's releases faked."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from license import analytics, keygen, token_bucket
from license.job_packs import catalog, github_releases, signature
from license.settings import config
from license.tests.github_fake import FakeGitHub
from license.tests.job_pack_portal import PackPortal
from license.tests.job_pack_samples import TEST_PACK_KEY, TEST_PACK_PUBLIC_KEY_HEX
from license.tests.test_license_routes import FakeKeygen


class CapturedEvents(list):
    """Every ``capture()`` the PostHog client received, as plain dicts."""

    def capture(self, event, *, distinct_id, properties, groups, disable_geoip):
        self.append(
            {
                "event": event,
                "distinct_id": distinct_id,
                "properties": properties,
                "disable_geoip": disable_geoip,
            }
        )

    def named(self, event: str) -> list[dict]:
        return [captured for captured in self if captured["event"] == event]


@pytest.fixture
def posthog_events(monkeypatch: pytest.MonkeyPatch) -> CapturedEvents:
    events = CapturedEvents()
    monkeypatch.setattr(analytics, "_client", events)
    monkeypatch.setattr(analytics, "_init_attempted", True)
    return events


@pytest.fixture
def trusted_pack_key(monkeypatch: pytest.MonkeyPatch) -> Ed25519PrivateKey:
    """The tests' key trusted as a release's is; the compiled list never holds it."""
    monkeypatch.setattr(signature, "PACK_PUBLIC_KEYS_HEX", (TEST_PACK_PUBLIC_KEY_HEX,))
    return TEST_PACK_KEY


@pytest.fixture
def pack_portal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PackPortal:
    """Keygen faked at its transport, Redis down, empty buckets, generous job-pack
    limits, an empty JOB_PACKS_DIR, no GitHub, and a fresh catalog."""
    fake = FakeKeygen()

    @asynccontextmanager
    async def http(client=None) -> AsyncIterator[httpx2.AsyncClient]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake.handle)
        ) as session:
            yield session

    def redis_down() -> None:
        raise OSError("no Redis in unit tests")

    packs = tmp_path / "job-packs"
    packs.mkdir()
    monkeypatch.setattr(keygen, "_http", http)
    monkeypatch.setattr(token_bucket, "_redis", redis_down)
    monkeypatch.setattr(token_bucket, "_memory_buckets", {})
    monkeypatch.setattr(catalog, "_shared", None)
    for name, value in {
        "KEYGEN_ACCOUNT_ID": "acct",
        "KEYGEN_API_TOKEN": "product-token",
        "KEYGEN_API_URL": "",
        "KEYGEN_HOST": "",
        "LICENSE_JOB_PACK_RATE_LIMIT_PER_HOUR": 100,
        "LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR": 100,
        "LICENSE_REFRESH_RATE_LIMIT_PER_HOUR": 100,
        "LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR": 100,
        "LICENSE_CLIENT_IP_HEADER": "x-real-ip",
        "JOB_PACKS_DIR": str(packs),
        "JOB_PACKS_GITHUB_REPO": "",
        "JOB_PACKS_GITHUB_TOKEN": "",
        "JOB_PACKS_CACHE_SECONDS": 600,
    }.items():
        monkeypatch.setattr(config, name, value)
    return PackPortal(fake, packs)


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    """The configured store is the fake's repository; request it after `pack_portal`."""
    fake = FakeGitHub()

    @asynccontextmanager
    async def http() -> AsyncIterator[httpx2.AsyncClient]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(fake.handle), follow_redirects=False
        ) as client:
            yield client

    monkeypatch.setattr(github_releases, "_http", http)
    monkeypatch.setattr(config, "JOB_PACKS_DIR", "")
    monkeypatch.setattr(config, "JOB_PACKS_GITHUB_REPO", fake.repo)
    monkeypatch.setattr(config, "JOB_PACKS_GITHUB_TOKEN", fake.token)
    return fake
