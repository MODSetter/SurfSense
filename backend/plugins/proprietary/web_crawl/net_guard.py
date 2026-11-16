"""Refuses crawl targets whose host is not publicly routable: loopback, private, link-local, metadata.

``::ffff:127.0.0.1`` reads ``is_loopback == False``, so mapped IPv4 is unwrapped
first; ``is_global`` (minus multicast) also refuses carrier-grade NAT, which a
union of the private flags admits. A name that will not resolve is refused. Not a
defence against DNS rebinding: the fetcher resolves again.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _resolve_host(host: str) -> list[str]:
    """Every address ``host`` resolves to, across both families."""
    return sorted(
        {
            info[4][0]
            for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        }
    )


def _is_public_address(raw: str) -> bool:
    """True when ``raw`` parses as an address the public internet can route to."""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        # Includes scoped forms such as ``fe80::1%eth0``, which are link-local
        # anyway; anything unparseable is refused rather than guessed at.
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return address.is_global and not address.is_multicast


def is_publicly_routable(url: str) -> bool:
    """True only when every address ``url``'s host resolves to is public.

    A host with both a public and a private answer is refused: the fetcher
    resolves independently and may pick either one.
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        return False
    host = parts.hostname
    if not host:
        return False

    # An address literal needs no resolver, and asking one would let a
    # nameserver answer for a host the URL already pinned.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return _is_public_address(host)

    try:
        addresses = _resolve_host(host)
    except (OSError, UnicodeError):
        return False
    if not addresses:
        return False
    return all(_is_public_address(address) for address in addresses)
