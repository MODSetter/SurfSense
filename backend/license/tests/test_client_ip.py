"""The rate limits' caller is the address the proxy in front writes in its one header, so
a header a caller sets cannot buy a bucket of its own.

Driven through the job pack route with a job SurfSense does not sell: it answers 422
once the limits pass, without asking Keygen, and 429 when the address bucket is empty.
"""

from __future__ import annotations

import logging

import pytest

from license.settings import config
from license.tests.job_pack_portal import PEER, PackPortal

pytestmark = pytest.mark.unit

UNSOLD = "JOB_NOT_SOLD"


@pytest.fixture
def one_request_per_address(pack_portal: PackPortal, monkeypatch) -> PackPortal:
    monkeypatch.setattr(config, "LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR", 1)
    return pack_portal


async def codes(portal: PackPortal, *callers: dict) -> list[int]:
    """One request per caller, each with a key of its own."""
    return [
        (await portal.ask(f"KEY-{n}", UNSOLD, **caller)).status_code
        for n, caller in enumerate(callers)
    ]


async def test_the_proxys_header_names_the_caller(
    one_request_per_address: PackPortal,
) -> None:
    answers = await codes(
        one_request_per_address,
        {"ip": "198.51.100.1"},
        {"ip": "198.51.100.2"},
        {"ip": "198.51.100.1"},
    )

    assert answers == [422, 422, 429]


async def test_a_forged_cf_connecting_ip_gets_no_bucket_of_its_own(
    one_request_per_address: PackPortal,
) -> None:
    """Any caller can send CF-Connecting-IP or X-Forwarded-For; only the proxy writes X-Real-IP."""
    answers = await codes(
        one_request_per_address,
        {"ip": "198.51.100.1", "headers": {"CF-Connecting-IP": "192.0.2.10"}},
        {
            "ip": "198.51.100.1",
            "headers": {
                "CF-Connecting-IP": "192.0.2.11",
                "X-Forwarded-For": "192.0.2.12",
            },
        },
    )

    assert answers == [422, 429]


async def test_another_header_can_be_named(
    one_request_per_address: PackPortal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cf-connecting-ip once Cloudflare fronts the host; a list counts by its first entry."""
    monkeypatch.setattr(config, "LICENSE_CLIENT_IP_HEADER", "cf-connecting-ip")
    behind_cloudflare = await codes(
        one_request_per_address,
        {"ip": "10.0.0.1", "headers": {"CF-Connecting-IP": "198.51.100.1"}},
        {"ip": "10.0.0.1", "headers": {"CF-Connecting-IP": "198.51.100.2"}},
        {"ip": "10.0.0.2", "headers": {"CF-Connecting-IP": "198.51.100.1"}},
    )
    monkeypatch.setattr(config, "LICENSE_CLIENT_IP_HEADER", "x-forwarded-for")
    forwarded = await codes(
        one_request_per_address,
        {"headers": {"X-Forwarded-For": "198.51.100.7, 10.0.0.1"}},
        {"headers": {"X-Forwarded-For": "198.51.100.7, 10.0.0.2"}},
    )

    assert behind_cloudflare == [422, 422, 429]
    assert forwarded == [422, 429]


async def test_without_the_header_the_socket_peer_is_used_and_named_once(
    one_request_per_address: PackPortal,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every caller then shares the proxy's bucket, so the operator is told which header is missing."""
    monkeypatch.setattr(config, "LICENSE_CLIENT_IP_HEADER", "x-test-proxy-address")

    with caplog.at_level(logging.WARNING, logger="license.client_ip"):
        answers = await codes(one_request_per_address, {"ip": None}, {"ip": None})

    warnings = [r for r in caplog.records if r.name == "license.client_ip"]
    assert answers == [422, 429]
    assert len(warnings) == 1
    assert "x-test-proxy-address" in warnings[0].getMessage()
    assert PEER[0] not in caplog.text


async def test_an_empty_setting_means_the_socket_peer_without_a_warning(
    one_request_per_address: PackPortal,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(config, "LICENSE_CLIENT_IP_HEADER", "")

    with caplog.at_level(logging.WARNING, logger="license.client_ip"):
        answers = await codes(
            one_request_per_address, {"ip": "198.51.100.1"}, {"ip": "198.51.100.2"}
        )

    assert answers == [422, 429]
    assert not [r for r in caplog.records if r.name == "license.client_ip"]
