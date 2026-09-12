"""``is_publicly_routable`` behavior: refuse URLs whose host is not public.

The literal-address cases need no resolver at all, so they exercise the real
code end to end; only the hostname cases stub ``_resolve_host``, because a unit
test cannot depend on what DNS answers.
"""

from __future__ import annotations

import socket

import pytest

from app.utils.crawl import is_publicly_routable, net_guard

pytestmark = pytest.mark.unit


def test_public_literal_is_allowed() -> None:
    assert is_publicly_routable("https://8.8.8.8/") is True


def test_loopback_literal_is_refused() -> None:
    assert is_publicly_routable("http://127.0.0.1:8000/health") is False


def test_cloud_metadata_literal_is_refused() -> None:
    """169.254.169.254 is the AWS/GCP/Azure credential endpoint."""
    assert is_publicly_routable("http://169.254.169.254/latest/meta-data/") is False


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://0.0.0.0/",
    ],
)
def test_private_and_unspecified_literals_are_refused(url: str) -> None:
    assert is_publicly_routable(url) is False


def test_ipv6_loopback_literal_is_refused() -> None:
    assert is_publicly_routable("http://[::1]:8000/") is False


def test_ipv4_mapped_ipv6_literal_is_refused() -> None:
    """``::ffff:127.0.0.1`` reports ``is_loopback == False``; only the mapped
    IPv4 form does, so a guard that reads the flags off the IPv6 object alone
    lets loopback through under its v6 spelling."""
    assert is_publicly_routable("http://[::ffff:127.0.0.1]/") is False


def test_carrier_grade_nat_literal_is_refused() -> None:
    """100.64.0.0/10 (RFC 6598) is none of private/loopback/link-local/reserved
    /multicast, so a guard built from those five flags admits it — but it is
    carrier-internal and not publicly routable."""
    assert is_publicly_routable("http://100.64.0.1/") is False


def test_multicast_literal_is_refused() -> None:
    """224.0.0.1 reports ``is_global == True``, so the routability check alone
    is not enough to exclude it."""
    assert is_publicly_routable("http://224.0.0.1/") is False


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "gopher://127.0.0.1/", "ftp://example.com/", "not a url"],
)
def test_non_http_scheme_is_refused(url: str) -> None:
    assert is_publicly_routable(url) is False


def test_hostname_resolving_to_a_private_address_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(net_guard, "_resolve_host", lambda _host: ["10.1.2.3"])

    assert is_publicly_routable("https://internal.example.com/") is False


def test_hostname_is_refused_when_any_answer_is_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host with both a public and a private answer must not be crawled: the
    fetcher resolves independently and may pick either."""
    monkeypatch.setattr(
        net_guard, "_resolve_host", lambda _host: ["93.184.216.34", "192.168.0.7"]
    )

    assert is_publicly_routable("https://split-horizon.example.com/") is False


def test_hostname_resolving_only_to_public_addresses_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        net_guard,
        "_resolve_host",
        lambda _host: ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"],
    )

    assert is_publicly_routable("https://example.com/page") is True


def test_unresolvable_hostname_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed: a name we cannot resolve is not a name we can clear."""

    def _boom(_host: str) -> list[str]:
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(net_guard, "_resolve_host", _boom)

    assert is_publicly_routable("https://does-not-exist.example/") is False


def test_hostname_resolving_to_nothing_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(net_guard, "_resolve_host", lambda _host: [])

    assert is_publicly_routable("https://empty.example/") is False
