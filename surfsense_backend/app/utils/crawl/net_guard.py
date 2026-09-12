"""Destination guard — refuses crawl targets that are not publicly routable.

``validators.url`` answers a syntactic question: is this a well-formed URL. It
says nothing about *where* the URL points, so ``http://127.0.0.1:8000/`` and
``http://169.254.169.254/latest/meta-data/`` (the cloud metadata endpoint) both
pass it and are then fetched from inside the backend's network namespace. This
module answers the other question — does the host resolve only to addresses the
public internet can reach — and is the gate the crawler consults before any
tier runs.

Two details decide correctness here:

* ``::ffff:127.0.0.1`` reports ``is_loopback == False``. The address flags only
  read true on the mapped IPv4 form, so the mapping is unwrapped before the
  address is judged; reading the flags off the IPv6 object admits loopback
  under its v6 spelling.
* ``is_global`` is the right primitive rather than a union of
  ``is_private``/``is_loopback``/``is_link_local``/``is_reserved``: that union
  admits carrier-grade NAT (``100.64.0.0/10``, RFC 6598), which is not
  publicly routable. ``is_global`` does report ``True`` for multicast, which is
  therefore excluded separately.

Resolution failures refuse. A name that cannot be resolved is not a name that
can be cleared, and failing open here would make an unreachable DNS server a
way past the guard.

This narrows the reachable surface; it is not a defence against DNS rebinding.
The fetcher resolves the host again on its own, so a name that answers
differently between this check and that fetch is out of scope for a
resolve-then-fetch guard.
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
